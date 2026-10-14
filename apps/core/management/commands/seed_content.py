import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.cache import bump_content_version
from apps.core.seeding import ContentSeeder


class Command(BaseCommand):
    help = "Load the website's bilingual seed content and media. Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(settings.BASE_DIR / "seed" / "content.json"))
        parser.add_argument("--media-dir", default=str(settings.BASE_DIR / "seed" / "media"))
        parser.add_argument(
            "--replace-media", action="store_true", help="Re-copy files even when a field already has one."
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Seed file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        seeder = ContentSeeder(
            data,
            Path(options["media_dir"]),
            replace_media=options["replace_media"],
            log=lambda msg: self.stdout.write(f"  {msg}"),
        )
        with transaction.atomic():
            seeder.run()
        bump_content_version()
        self.stdout.write(self.style.SUCCESS("Content seeded."))
