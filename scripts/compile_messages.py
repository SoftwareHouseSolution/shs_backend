"""Compile every apps/*/locale/*/LC_MESSAGES/django.po to .mo without GNU gettext.

`python manage.py compilemessages` does the same job but needs the `msgfmt` binary, which
Windows machines rarely have. This implements the subset of the .po format the project
uses (msgctxt-free entries, multi-line strings, fuzzy flags skipped).

    python scripts/compile_messages.py
"""

import ast
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_po(path: Path) -> dict[str, str]:
    messages: dict[str, str] = {}
    msgid = msgstr = None
    target = None
    fuzzy = False

    def flush():
        nonlocal msgid, msgstr, fuzzy
        if msgid is not None and msgstr is not None and not fuzzy and (msgstr or msgid == ""):
            messages[msgid] = msgstr
        msgid = msgstr = None
        fuzzy = False

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#,") and "fuzzy" in line:
            flush()
            fuzzy = True
        elif line.startswith("msgid "):
            if msgid is not None:
                keep_fuzzy = fuzzy
                flush()
                fuzzy = keep_fuzzy
            msgid, target = ast.literal_eval(line[6:]), "id"
        elif line.startswith("msgstr "):
            msgstr, target = ast.literal_eval(line[7:]), "str"
        elif line.startswith('"'):
            if target == "id":
                msgid += ast.literal_eval(line)
            elif target == "str":
                msgstr += ast.literal_eval(line)
        elif not line:
            flush()
    flush()
    return messages


def write_mo(messages: dict[str, str], path: Path) -> None:
    keys = sorted(messages)
    ids = b"".join(k.encode() + b"\0" for k in keys)
    strs = b"".join(messages[k].encode() + b"\0" for k in keys)
    n = len(keys)
    key_start = 7 * 4 + 16 * n
    value_start = key_start + len(ids)
    offsets_ids, offsets_strs = [], []
    pos = 0
    for k in keys:
        b = k.encode()
        offsets_ids += [len(b), key_start + pos]
        pos += len(b) + 1
    pos = 0
    for k in keys:
        b = messages[k].encode()
        offsets_strs += [len(b), value_start + pos]
        pos += len(b) + 1
    header = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + 8 * n, 0, 0)
    path.write_bytes(
        header
        + struct.pack(f"{2 * n}i", *offsets_ids)
        + struct.pack(f"{2 * n}i", *offsets_strs)
        + ids
        + strs
    )


def main() -> int:
    count = 0
    for po in ROOT.glob("apps/*/locale/*/LC_MESSAGES/*.po"):
        messages = parse_po(po)
        write_mo(messages, po.with_suffix(".mo"))
        print(f"{po.relative_to(ROOT)}: {len(messages) - 1} messages")
        count += 1
    if not count:
        print("No .po files found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
