"""Recording visits. Testable without HTTP: call `record()` with a payload and a UA string.

The browser reports each page view by its own random `view_id`, more than once: when the
page opens (duration 0), periodically while it stays visible, and when it is left. Every
report is an idempotent upsert on that id, and duration only ever grows — so a lost,
duplicated or out-of-order report cannot corrupt the timeline.
"""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone

from .models import PageView, VisitSession
from .user_agents import classify

# A single page reporting more than this is a tab left open, not reading time.
MAX_VIEW_DURATION_MS = 30 * 60 * 1000


@dataclass(frozen=True)
class ViewReport:
    session_id: UUID
    visitor_id: UUID
    view_id: UUID
    path: str
    language: str = ""
    referrer: str = ""
    duration_ms: int = 0


def _referrer_host(referrer: str, own_host: str) -> str:
    host = (urlparse(referrer).hostname or "") if referrer else ""
    # Internal navigation is not a source; only the outside site a visit came from is.
    return "" if host == own_host else host[:255]


class AnalyticsService:
    def __init__(self, clock=timezone.now):
        self._now = clock

    def record(self, report: ViewReport, *, user_agent: str, site_host: str = "") -> bool:
        """Store or update one page view. Returns False when the report was ignored (bots)."""
        client = classify(user_agent)
        if client.is_bot:
            return False

        now: datetime = self._now()
        duration = max(0, min(report.duration_ms, MAX_VIEW_DURATION_MS))
        session = self._session(report, client, now, site_host)

        updated = PageView.objects.filter(view_id=report.view_id, session=session).update(
            duration_ms=Greatest(F("duration_ms"), duration)
        )
        if not updated:
            try:
                with transaction.atomic():
                    PageView.objects.create(
                        view_id=report.view_id,
                        session=session,
                        sequence=session.views.count() + 1,
                        path=report.path,
                        entered_at=now,
                        duration_ms=duration,
                    )
            except IntegrityError:
                # A concurrent report created it first (or the id belongs to another
                # session, which is ignored). Apply the duration to the winner.
                PageView.objects.filter(view_id=report.view_id, session=session).update(
                    duration_ms=Greatest(F("duration_ms"), duration)
                )
        VisitSession.objects.filter(pk=session.pk).update(last_seen_at=now)
        return True

    def _session(self, report: ViewReport, client, now: datetime, site_host: str) -> VisitSession:
        defaults = {
            "visitor_id": report.visitor_id,
            "started_at": now,
            "last_seen_at": now,
            "language": report.language,
            "landing_path": report.path,
            "referrer_host": _referrer_host(report.referrer, site_host),
            "device": client.device,
            "browser": client.browser,
            "os": client.os,
        }
        try:
            with transaction.atomic():
                session, _created = VisitSession.objects.get_or_create(
                    session_id=report.session_id, defaults=defaults
                )
        except IntegrityError:  # lost a creation race — the row exists now
            session = VisitSession.objects.get(session_id=report.session_id)
        return session
