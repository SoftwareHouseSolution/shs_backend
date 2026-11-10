"""Company profile PDF (exported from Canva) -> clients.json + one WebP logo per client.

The output is what `manage.py import_clients` reads. The whole round trip:

    1. In Canva: Share > Download > PDF Standard, for the company profile.
    2. python scripts/extract_canva_clients.py "Company Profile.pdf" import/
    3. Look through import/logos/ — one file per client, named by page and client.
    4. python manage.py import_clients import/clients.json            (dry run: read the report)
    5. python manage.py import_clients import/clients.json --apply

Needs pymupdf, pillow and numpy, which are not in requirements.txt: nothing on the server
touches the PDF. Install them in a throwaway venv rather than the project's.

How a page is read. Each client is a box: the name in large type (two lines, left-, centre-
or right-aligned), then location and business types in small type, then the logo below.
A page holds one or two rows of four. Name lines are stacked into boxes by horizontal
overlap, each small line joins the nearest box above it, and the logo is whatever is drawn
between the box's text and the next row.

Things learnt the hard way:

  - Logos are RENDERED from the page, never pulled out of the file. Canva reuses one
    embedded image for several different logos on a page, so extracting by image gives the
    wrong logo.
  - The rule between the two rows is a vector line; a logo's box runs down to the next row,
    so it is cut at that line or every top-row logo carries a stripe under it. On some
    pages the rule is 6pt thick, not 1pt.
  - The region comes from the section heading ("Clients in Sharqia"), not the location,
    which is free text. Pages without a heading continue the previous section.
"""

import argparse
import json
import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)  # fitz's rename notice

import fitz  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

BG = np.array([239, 237, 236])  # the profile's page grey
PAPER = np.array([250, 250, 248])  # the website's --paper; every logo sits on it
ZOOM = 3
TYPES = ("manufacturing", "wholesale", "retail")

# Section headings -> the website's region keys (Regions in the admin).
REGION_OF = {
    "cairo": "greater-cairo",
    "giza": "giza",
    "alexandria": "alexandria",
    **dict.fromkeys(
        ["dakahlia", "kafr el sheikh", "gharbia", "beheira", "qalyubia", "damietta", "monufia", "sharqia"]
        + ["port said", "ismailia", "suez"],
        "delta-canal",
    ),
    **dict.fromkeys(["assiut", "fayoum", "sohag", "minya", "qena", "beni suef", "aswan", "luxor"], "upper-egypt"),
    **dict.fromkeys(["hurghada", "red sea", "sinai", "south sinai", "north sinai"], "sinai-red-sea"),
    "outside egypt": "international",
    # No region of its own on the site; the North Coast is closest to Alexandria.
    "marsa matrouh": "alexandria",
}

# Typos in the design itself, corrected here rather than carried onto the website.
FIX_TEXT = {"Helio": ["Heliopolis"], "polisRetail": ["Retail"]}
FIX_NAME = {"El Nabil Gold Gold & Diamond": "El Nabil Gold & Diamond"}
NOT_A_LOCATION = {"Gold"}


def text_lines(page):
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            raw = " ".join("".join(s["text"] for s in line["spans"]).split())
            for t in FIX_TEXT.get(raw, [raw]) if raw else []:
                x0, y0, x1, y1 = line["bbox"]
                out.append({"t": t, "x": x0, "x1": x1, "y": y0, "y1": y1, "s": line["spans"][0]["size"]})
    return out


def heading_of(lines):
    # Top-left only: a logo set as live text ("Joly PEAR" on page 26) can be just as large.
    big = sorted((ln for ln in lines if ln["s"] >= 60 and ln["x"] < 150 and ln["y"] < 320), key=lambda ln: ln["y"])
    return " ".join(ln["t"] for ln in big)


def gap(a0, a1, b0, b1):
    """Horizontal distance between two spans; 0 when they overlap."""
    return max(0, max(a0, b0) - min(a1, b1))


def boxes(page, lines):
    body = [
        ln
        for ln in lines
        if ln["s"] < 60 and ln["t"] not in ("Software House Solution", "-") and not re.fullmatch(r"\d+", ln["t"])
    ]
    names = sorted((ln for ln in body if ln["s"] > 22), key=lambda ln: (ln["y"], ln["x"]))
    small = [ln for ln in body if ln["s"] <= 22]

    cells = []
    for ln in names:
        for c in cells:
            if gap(c["x"], c["x1"], ln["x"], ln["x1"]) == 0 and 0 < ln["y"] - c["name"][-1]["y"] < 40:
                c["name"].append(ln)
                c["x"], c["x1"] = min(c["x"], ln["x"]), max(c["x1"], ln["x1"])
                break
        else:
            cells.append({"x": ln["x"], "x1": ln["x1"], "y": ln["y"], "name": [ln], "small": []})

    orphans = []
    for ln in sorted(small, key=lambda ln: ln["y"]):
        best = None
        for c in cells:
            if -4 < ln["y"] - c["name"][-1]["y1"] < 110:
                d = gap(c["x"], c["x1"], ln["x"], ln["x1"]) + abs(c["x"] - ln["x"]) * 0.1
                if d < 160 and (best is None or d < best[0]):
                    best = (d, c)
        if best:
            best[1]["small"].append(ln)
        else:
            orphans.append(ln["t"])
    for c in cells:
        c["x"] = min([c["x"]] + [ln["x"] for ln in c["small"]])

    drawings = [g["rect"] for g in page.get_drawings()]
    rules_y = [r.y0 for r in drawings if r.width > 1000 and r.height < 10]
    rules_x = [r.x1 for r in drawings if r.height > 600 and r.width < 6]
    width, height = page.rect.width, page.rect.height
    for c in cells:
        right = [d["x"] for d in cells if abs(d["y"] - c["y"]) < 60 and d["x"] > c["x"] + 100]
        below = [d["y"] for d in cells if d["y"] > c["y"] + 150]
        top = max(ln["y1"] for ln in c["name"] + c["small"]) + 6
        rect = fitz.Rect(
            max(0, c["x"] - 40),
            top,
            min(min(right) - 40 if right else c["x"] + 360, width),
            min(below) - 12 if below else height,
        )
        for y in rules_y:
            if rect.y0 < y < rect.y1:
                rect.y1 = y - 3
        for x in rules_x:
            if rect.x0 < x < rect.x1:
                rect.x0 = x + 3
        c["rect"] = rect
    return sorted(cells, key=lambda c: (round(c["y"] / 100), c["x"])), orphans


def render_logo(page, rect, dest) -> bool:
    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), clip=rect)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[..., :3].astype(np.int16)
    ink = np.abs(a - BG).max(axis=2) > 22
    # A row or column only counts with a few inked pixels in it, so specks do not widen the crop.
    rows, cols = np.where(ink.sum(1) > 2)[0], np.where(ink.sum(0) > 2)[0]
    if len(rows) == 0 or len(cols) == 0:
        return False
    crop = a[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1].astype(np.float32)
    # Re-base the page grey onto the site's paper: background becomes PAPER exactly, ink keeps
    # its colour, and anti-aliased edges blend between the two.
    t = np.clip(np.abs(crop - BG).max(axis=2, keepdims=True) / 60.0, 0, 1)
    logo = (PAPER * (1 - t) + crop * t).clip(0, 255).astype(np.uint8)
    pad = 24
    canvas = np.empty((logo.shape[0] + 2 * pad, logo.shape[1] + 2 * pad, 3), np.uint8)
    canvas[:] = PAPER
    canvas[pad:-pad, pad:-pad] = logo
    im = Image.fromarray(canvas)
    if im.height > 300:  # the same height as the logos already on the site
        im = im.resize((round(im.width * 300 / im.height), 300), Image.LANCZOS)
    if im.width > 640:
        im = im.resize((640, round(im.height * 640 / im.width)), Image.LANCZOS)
    im.save(dest, "WEBP", quality=90, method=6)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("out", type=Path, help="folder for clients.json and logos/")
    args = parser.parse_args()

    doc = fitz.open(args.pdf)
    (args.out / "logos").mkdir(parents=True, exist_ok=True)
    clients, region, sector, in_section = [], None, "jewellery", False
    for n, page in enumerate(doc, 1):
        lines = text_lines(page)
        heading = heading_of(lines)
        if heading:
            is_clients = "client" in heading.lower()
            if in_section and not is_clients:
                break  # past the client pages ("Let's Build Together")
            in_section = in_section or is_clients
            if is_clients:
                sector = "enterprise" if "erp" in heading.lower() else "jewellery"
                m = re.search(r"clients(?: in)? (.+)$", heading, re.I)
                region = REGION_OF.get(m.group(1).strip().lower()) if m else None
                if m and not region:
                    print(f"page {n}: no region for the heading {m.group(1)!r} - add it to REGION_OF")
        if not in_section:
            continue
        cells, orphans = boxes(page, lines)
        if orphans:
            print(f"page {n}: text not attached to any client: {orphans}")
        for c in cells:
            name = " ".join(ln["t"] for ln in c["name"])
            name = FIX_NAME.get(name, name)
            texts = [ln["t"] for ln in c["small"]]
            is_type = [bool(set(re.findall(r"[a-z]+", t.lower())) & set(TYPES)) for t in texts]
            location = " ".join(t for t, typ in zip(texts, is_type, strict=True) if not typ)
            location = "" if location in NOT_A_LOCATION else location
            type_text = " ".join(t for t, typ in zip(texts, is_type, strict=True) if typ).lower()
            logo = f"logos/p{n:02d}-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}.webp"
            if not render_logo(page, c["rect"], args.out / logo):
                print(f"page {n}: no logo found for {name!r}")
                logo = None
            clients.append(
                {
                    "page": n,
                    "name": name,
                    "location": location,
                    # ERP clients sit under one heading; their location says which city.
                    "region": REGION_OF.get(location.lower(), "greater-cairo") if sector == "enterprise" else region,
                    "sector": sector,
                    "business_types": [t for t in TYPES if t in type_text],
                    "logo": logo,
                }
            )
    (args.out / "clients.json").write_text(json.dumps(clients, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(clients)} clients written to {args.out / 'clients.json'}")


if __name__ == "__main__":
    main()
