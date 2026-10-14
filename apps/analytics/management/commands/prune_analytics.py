from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.models import VisitSession


class Command(BaseCommand):
    help = "Delete visits (and their page views) older than ANALYTICS_RETENTION_DAYS. Schedule daily."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="Override the retention period.")

    def handle(self, *args, days=None, **options):
        keep = days if days is not None else settings.ANALYTICS_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=keep)
        deleted, _ = VisitSession.objects.filter(started_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} records older than {keep} days."))
