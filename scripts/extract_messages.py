"""List translatable strings that have no Arabic translation yet — a gettext-free stand-in
for `makemessages` on machines without GNU gettext.

Scans the project (apps/, config/, templates/) and the Unfold admin theme (which ships no
Arabic catalogue), drops strings Django's own Arabic catalogues already translate, and
drops strings already present in apps/core/locale/ar/LC_MESSAGES/django.po.

    python scripts/extract_messages.py            # prints missing msgids as a JSON list
"""

import ast
import gettext
import json
import re
import sys
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PO = ROOT / "apps/core/locale/ar/LC_MESSAGES/django.po"

GETTEXT_FUNCS = {"_", "gettext", "gettext_lazy", "ngettext", "ngettext_lazy", "pgettext", "pgettext_lazy"}
TEMPLATE_PATTERNS = [
    re.compile(r"""\{%\s*(?:trans|translate)\s+"((?:[^"\\]|\\.)*)"(?:\s+[^%]*)?%\}"""),
    re.compile(r"""\{%\s*(?:trans|translate)\s+'((?:[^'\\]|\\.)*)'(?:\s+[^%]*)?%\}"""),
    re.compile(r"""\b_\("((?:[^"\\]|\\.)*)"\)"""),
    re.compile(r"""\b_\('((?:[^'\\]|\\.)*)'\)"""),
]
BLOCK = re.compile(r"\{%\s*(?:blocktrans|blocktranslate)(?:\s+[^%]*)?%\}(.*?)\{%\s*end(?:blocktrans|blocktranslate)\s*%\}", re.S)


def from_python(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if name in GETTEXT_FUNCS and node.args:
                arg = node.args[1] if name.startswith("pgettext") and len(node.args) > 1 else node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.add(arg.value)
    return found


def from_template(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = {m.encode().decode("unicode_escape") if "\\" in m else m for rx in TEMPLATE_PATTERNS for m in rx.findall(text)}
    for body in BLOCK.findall(text):
        found.add(re.sub(r"\{\{\s*(\w+)\s*\}\}", r"%(\1)s", body.strip()))
    return found


def existing_po() -> set[str]:
    if not PO.exists():
        return set()
    from compile_messages import parse_po  # same directory; handles escapes and multi-line entries

    return set(parse_po(PO))


def django_translated() -> gettext.NullTranslations:
    """Arabic catalogues Django will actually load: core, the INSTALLED django.contrib apps,
    and DRF. Uninstalled apps (admindocs, flatpages…) are excluded — their catalogues
    contain common words like "Views" and "title" that would otherwise mask our own."""
    import rest_framework
    from django.conf import settings

    base = Path(django.__file__).parent
    installed = {a.split(".")[-1] for a in settings.INSTALLED_APPS if a.startswith("django.contrib.")}
    dirs = [base / "conf/locale", *(base / "contrib" / app / "locale" for app in sorted(installed))]
    dirs.append(Path(rest_framework.__file__).parent / "locale")
    chain = None
    for d in dirs:
        try:
            t = gettext.translation("django", d, languages=["ar"])
        except FileNotFoundError:
            continue
        if chain is None:
            chain = t
        else:
            chain.add_fallback(t)
    return chain or gettext.NullTranslations()


def main() -> int:
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()
    import unfold

    sources: set[str] = set()
    for folder in ("apps", "config", "templates"):
        for path in (ROOT / folder).rglob("*"):
            if "migrations" in path.parts or "tests" in path.parts:
                continue
            if path.suffix == ".py":
                sources |= from_python(path)
            elif path.suffix in {".html", ".txt"}:
                sources |= from_template(path)
    unfold_dir = Path(unfold.__file__).parent
    # Unfold's optional integrations (import-export, reversion, …) are skipped unless they
    # are installed here; their strings never appear in this admin.
    from django.conf import settings

    installed_contrib = {app.split(".")[-1] for app in settings.INSTALLED_APPS if app.startswith("unfold.contrib.")}
    for path in unfold_dir.rglob("*"):
        rel = path.relative_to(unfold_dir).parts
        if rel[0] == "contrib" and len(rel) > 1 and rel[1] not in installed_contrib:
            continue
        if any(part.startswith("contrib") for part in rel[1:2]) and rel[0] == "templates" and len(rel) > 2 and rel[2] not in installed_contrib:
            continue
        if path.suffix == ".py":
            sources |= from_python(path)
        elif path.suffix == ".html":
            sources |= from_template(path)

    known = django_translated()
    have = existing_po()
    missing = sorted(
        s for s in sources
        if s.strip() and s not in have and known.gettext(s) == s
        and not re.fullmatch(r"[A-Z]+_[A-Z_]+", s)  # format keys such as DATETIME_FORMAT
        and "{% plural %}" not in s  # plural forms: Django's catalogue covers the ones shown
    )
    json.dump(missing, sys.stdout, ensure_ascii=False, indent=0)
    print(f"\n{len(missing)} strings need Arabic", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
