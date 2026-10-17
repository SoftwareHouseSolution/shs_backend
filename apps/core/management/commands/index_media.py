from collections import defaultdict

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.media import media_files, referenced_media
from apps.core.models import StoredFile
from apps.core.storage import content_digest


def _mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


class Command(BaseCommand):
    help = (
        "Hash every file in the media folder and rebuild the index that stops identical "
        "uploads being stored twice. Run once after deploying, or after copying media in by "
        "hand. Reads files only; never moves or deletes them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Do nothing when the index already has entries (for container start-up).",
        )

    def handle(self, *args, if_empty=False, **options):
        if if_empty and StoredFile.objects.exists():
            self.stdout.write("  Media index already built; skipping.")
            return
        referenced = referenced_media()
        groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for name, path in media_files():
            with path.open("rb") as fh:
                groups[content_digest(File(fh))].append((name, path.stat().st_size))

        rows = []
        duplicate_groups = wasted = 0
        for digest, copies in groups.items():
            # The copy the database uses is the one a re-upload should point at.
            copies.sort(key=lambda c: (c[0] not in referenced, c[0]))
            rows.append(StoredFile(sha256=digest, name=copies[0][0], size=copies[0][1]))
            if len(copies) > 1:
                duplicate_groups += 1
                wasted += sum(size for _name, size in copies[1:])

        with transaction.atomic():
            StoredFile.objects.all().delete()
            StoredFile.objects.bulk_create(rows, batch_size=500)

        files = sum(len(c) for c in groups.values())
        self.stdout.write(f"  {files} files, {len(rows)} distinct.")
        if duplicate_groups:
            self.stdout.write(
                f"  {duplicate_groups} files already have identical copies "
                f"({_mb(wasted)} could be freed; see the admin System status page)."
            )
        self.stdout.write(self.style.SUCCESS("Media index rebuilt."))
