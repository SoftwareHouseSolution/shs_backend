from django.core.management.base import BaseCommand

from apps.core import system_status
from apps.core.system_status import ERROR, WARNING

MARKS = {"ok": "ok", "info": "--", "warning": "!!", "error": "XX"}


class Command(BaseCommand):
    help = (
        "Print the same health report as Admin > System > System status. Exits with status 1 "
        "when a check fails (or, with --strict, on any warning), so cron or CI can alert on it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    def handle(self, *args, strict=False, **options):
        report = system_status.build_report(use_cache=False)
        for section in report.sections:
            self.stdout.write(self.style.MIGRATE_HEADING(f"{section.title} [{section.status}]"))
            for check in section.checks:
                line = f"  {MARKS[check.status]} {check.label}: {check.value}"
                if check.detail and check.status in (WARNING, ERROR):
                    line += f"  ({check.detail})"
                style = {ERROR: self.style.ERROR, WARNING: self.style.WARNING}.get(check.status, str)
                self.stdout.write(style(line))
        self.stdout.write(f"\n{report.headline} ({report.duration_ms} ms)")
        failed = report.count(ERROR) or (strict and report.count(WARNING))
        if failed:
            raise SystemExit(1)
