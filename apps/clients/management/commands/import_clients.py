"""Load a client list into the roster: `clients.json` plus a folder of logos beside it.

    python manage.py import_clients path/to/clients.json             # dry run: report only
    python manage.py import_clients path/to/clients.json --apply     # add the new clients
    python manage.py import_clients path/to/clients.json --apply --update

The file is what scripts/extract_canva_clients.py writes from the company profile, but any
list of objects with these keys works:

    name, location, region (key), sector (key), business_types ([keys]), logo (path relative
    to the JSON file), and optionally slug, to match an existing client explicitly.

Without --apply nothing is written; the report says what would happen. Without --update
existing clients are never touched, only listed when the file disagrees with them. A blank
location or an empty type list in the file never clears a value the database has: a missing
cell in the design is not an instruction to delete.

Clients in the database but not in the file are reported and left alone. Removing one is a
decision for the admin, not something a re-export should do silently.
"""

import json
import re
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.clients.models import BusinessType, Client, Region, Sector
from apps.core.cache import bump_content_version

TRADE_SUFFIX = re.compile(r"(jewe?l+e?r?y|jewellery|jewels)$")


def name_key(name: str) -> str:
    """Spelling-insensitive identity: "Ghazal jewelry" and "Ghazal Jewellery" are one shop."""
    return TRADE_SUFFIX.sub("", re.sub(r"[^a-z0-9]", "", name.lower()))


def loc_key(location: str) -> str:
    return re.sub(r"[^a-z0-9]", "", location.lower())


class Command(BaseCommand):
    help = "Add clients (and their logos) from a clients.json file. Dry run unless --apply."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--apply", action="store_true", help="Write to the database. Without it, only report.")
        parser.add_argument(
            "--update", action="store_true", help="Also change existing clients where the file differs."
        )
        parser.add_argument(
            "--replace-logos", action="store_true", help="With --update, also replace existing clients' logos."
        )

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        rows = json.loads(path.read_text(encoding="utf-8"))
        regions = {r.key: r for r in Region.objects.all()}
        sectors = {s.key: s for s in Sector.objects.all()}
        types = {t.key: t for t in BusinessType.objects.all()}
        existing = list(Client.objects.select_related("region", "sector").prefetch_related("business_types"))
        by_slug = {c.slug: c for c in existing}
        by_key: dict[str, list[Client]] = {}
        for c in existing:
            by_key.setdefault(name_key(c.name), []).append(c)
        taken = set(by_slug)
        used: set[str] = set()

        def exact(row) -> Client | None:
            if row.get("slug") in by_slug:
                return by_slug[row["slug"]]
            free = [c for c in by_key.get(name_key(row["name"]), []) if c.slug not in used]
            if free:
                return next((c for c in free if loc_key(c.location) == loc_key(row["location"])), free[0])
            return None

        def glued(row) -> Client | None:
            # An earlier PDF import glued the start of the location onto some names ("Gerges
            # Ghali New"). Claim such a record rather than adding the shop a second time. Only
            # after every exact match is taken: "Salem Jewelry" must not claim "Salem Jewelry
            # Store" when the file lists that shop too.
            prefix = row["name"].lower() + " "
            found = [c for c in existing if c.slug not in used and c.name.lower().startswith(prefix)]
            return found[0] if len(found) == 1 else None

        matches: list[Client | None] = []
        for row in rows:
            matches.append(exact(row))
            if matches[-1]:
                used.add(matches[-1].slug)
        for i, row in enumerate(rows):
            if not matches[i] and (client := glued(row)):
                matches[i] = client
                used.add(client.slug)

        new, changed, same, skipped, repeats = [], [], 0, [], []
        listed: set[tuple[str, str]] = set()
        for row, client in zip(rows, matches, strict=True):
            problem = self.problem(row, path.parent, regions, sectors, types)
            # A second row with the same name and address that no existing client is left to
            # match is the same shop shown on two pages, not a new one. Two such rows that
            # each match a client of their own (two "Minous Gold" in Sagha) are two shops.
            ident = (name_key(row["name"]), loc_key(row["location"]))
            if not client and ident in listed:
                repeats.append(row)
                continue
            listed.add(ident)
            if client:
                diff = self.diff(client, row)
                if diff:
                    changed.append((client, row, diff))
                else:
                    same += 1
            elif problem:
                skipped.append((row, problem))
            else:
                new.append(row)
        missing = [c for c in existing if c.slug not in used]

        self.report(new, changed, same, skipped, missing, repeats, opts["update"])
        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("\nDry run: nothing was written. Add --apply to import."))
            return

        with transaction.atomic():
            for row in new:
                slug = base = slugify(row["name"]) or "client"
                n = 2
                while slug in taken:
                    slug, n = f"{base}-{n}", n + 1
                taken.add(slug)
                client = Client(
                    slug=slug,
                    name=row["name"],
                    location=row["location"],
                    region=regions[row["region"]],
                    sector=sectors[row["sector"]],
                )
                self.save_logo(client, path.parent / row["logo"])
                client.save()
                client.business_types.set([types[k] for k in row["business_types"]])
            if opts["update"]:
                for client, row, diff in changed:
                    for field, (_, value) in diff.items():
                        if field == "region":
                            client.region = regions[value]
                        elif field == "sector":
                            client.sector = sectors[value]
                        elif field != "business_types":
                            setattr(client, field, value)
                    if opts["replace_logos"] and row.get("logo") and (path.parent / row["logo"]).exists():
                        self.save_logo(client, path.parent / row["logo"])
                    client.save()
                    if "business_types" in diff:
                        client.business_types.set([types[k] for k in row["business_types"]])
        bump_content_version()
        done = f"Added {len(new)} clients."
        if opts["update"]:
            done += f" Updated {len(changed)}."
        self.stdout.write(self.style.SUCCESS(f"\n{done}"))

    @staticmethod
    def problem(row, base, regions, sectors, types) -> str | None:
        if row.get("region") not in regions:
            return f"unknown region {row.get('region')!r}"
        if row.get("sector") not in sectors:
            return f"unknown sector {row.get('sector')!r}"
        if unknown := [k for k in row.get("business_types", []) if k not in types]:
            return f"unknown business types {unknown}"
        if not row.get("logo") or not (base / row["logo"]).exists():
            return "no logo (a client needs one to be shown)"
        return None

    @staticmethod
    def diff(client: Client, row) -> dict:
        out = {}
        if row["name"] != client.name:
            out["name"] = (client.name, row["name"])
        if row["location"] and loc_key(row["location"]) != loc_key(client.location):
            out["location"] = (client.location, row["location"])
        if row.get("region") and row["region"] != client.region.key:
            out["region"] = (client.region.key, row["region"])
        if row.get("sector") and row["sector"] != client.sector.key:
            out["sector"] = (client.sector.key, row["sector"])
        current = sorted(t.key for t in client.business_types.all())
        if row.get("business_types") and sorted(row["business_types"]) != current:
            out["business_types"] = (current, sorted(row["business_types"]))
        return out

    @staticmethod
    def save_logo(client: Client, source: Path) -> None:
        with source.open("rb") as fh:
            client.logo.save(f"{client.slug}{source.suffix}", File(fh), save=False)

    def report(self, new, changed, same, skipped, missing, repeats, update):
        w = self.stdout.write
        w(
            f"{len(new)} new, {len(changed)} differ, {same} unchanged, {len(skipped)} skipped, "
            f"{len(missing)} in the database but not in the file, {len(repeats)} listed twice."
        )
        if new:
            w("\nNew clients:")
            for r in new:
                w(f"  + {r['name']}  ({r['location'] or '-'}, {r['region']})")
        if changed:
            w(
                "\nExisting clients the file differs from"
                + ("" if update else " (left as they are without --update)")
                + ":"
            )
            for c, _, diff in changed:
                w(f"  ~ {c.name}: " + "; ".join(f"{f} {a!r} -> {b!r}" for f, (a, b) in diff.items()))
        if skipped:
            w("\nSkipped:")
            for r, why in skipped:
                w(f"  ! {r['name']}: {why}")
        if repeats:
            w("\nListed twice in the file (imported once):")
            for r in repeats:
                w(f"  = {r['name']}  ({r['location'] or '-'})")
        if missing:
            w("\nIn the database but not in the file (left alone):")
            for c in missing:
                w(f"  ? {c.name}  ({c.location})")
