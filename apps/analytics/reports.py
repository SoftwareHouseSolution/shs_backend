"""Read side: what the admin and the dashboard show. Paths are shown as page names taken
from the CMS ("/ar/our-team" → "Our Team"), so the flow reads like the menu, not like URLs."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import get_language_bidi
from django.utils.translation import gettext as _

from .models import PageView, VisitSession

_LOCALE = re.compile(r"^/(en|ar)(?=/|$)")


def normalise_path(path: str) -> str:
    """Drop the language prefix and the trailing slash: /ar/customers/ → /customers."""
    stripped = _LOCALE.sub("", path or "") or "/"
    return stripped.rstrip("/") or "/"


def page_titles() -> dict[str, str]:
    """Normalised path → page name in the active language, from the CMS. One query."""
    from apps.pages.models import Page

    titles = {"/": _("Home")}
    # Attribute access, not values_list: it resolves the active language with fallback,
    # so the Arabic admin shows Arabic page names.
    for page in Page.objects.only("slug", "title_en", "title_ar"):
        titles[f"/{page.slug}"] = page.title
    return titles


def label_for(path: str, titles: dict[str, str]) -> str:
    return titles.get(normalise_path(path), normalise_path(path))


def format_duration(ms: int | float | None) -> str:
    """Compact, in the active language: 4s / 1m 05s / 1h 02m (٤ ث / ١ د ٠٥ ث …)."""
    seconds = int(round((ms or 0) / 1000))
    if seconds < 60:
        return _("%(s)ds") % {"s": seconds}
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return _("%(m)dm %(s)02ds") % {"m": minutes, "s": seconds}
    hours, minutes = divmod(minutes, 60)
    return _("%(h)dh %(m)02dm") % {"h": hours, "m": minutes}


def flow_arrow() -> str:
    """The flow reads in the interface's direction, so in Arabic the arrow points left."""
    return "←" if get_language_bidi() else "→"


@dataclass(frozen=True)
class Step:
    label: str
    path: str
    duration: str
    duration_ms: int


def flow(session: VisitSession, titles: dict[str, str]) -> list[Step]:
    return [
        Step(label_for(v.path, titles), v.path, format_duration(v.duration_ms), v.duration_ms)
        for v in sorted(session.views.all(), key=lambda v: (v.sequence, v.entered_at))
    ]


@dataclass(frozen=True)
class JourneyStop:
    """Consecutive views of one page merged: Home → Home → Home reads as one stop, ×3."""

    label: str
    path: str
    entered_at: datetime
    views: int
    duration: str
    duration_ms: int
    pct: int  # of the longest stop, for the bar


@dataclass(frozen=True)
class PageShare:
    label: str
    views: int
    duration: str
    pct: int  # of the visit's total time


@dataclass(frozen=True)
class VisitReport:
    total: str
    page_views: int
    unique_pages: int
    avg_per_page: str
    entry: str
    exit: str
    journey: list[JourneyStop]
    pages: list[PageShare]


def visit_report(session: VisitSession, titles: dict[str, str]) -> VisitReport:
    """Everything the visit's admin page shows, from the session's prefetched views."""
    views = sorted(session.views.all(), key=lambda v: (v.sequence, v.entered_at))
    total_ms = sum(v.duration_ms for v in views)

    merged: list[list] = []  # [label, path, entered_at, views, ms]
    per_page: dict[str, list[int]] = {}  # label → [views, ms]
    for v in views:
        label = label_for(v.path, titles)
        if merged and merged[-1][0] == label:
            merged[-1][3] += 1
            merged[-1][4] += v.duration_ms
        else:
            merged.append([label, v.path, v.entered_at, 1, v.duration_ms])
        views_ms = per_page.setdefault(label, [0, 0])
        views_ms[0] += 1
        views_ms[1] += v.duration_ms

    longest = max((m[4] for m in merged), default=0)
    journey = [
        JourneyStop(label, path, at, n, format_duration(ms), ms, round(100 * ms / longest) if longest else 0)
        for label, path, at, n, ms in merged
    ]
    pages = [
        PageShare(label, n, format_duration(ms), round(100 * ms / total_ms) if total_ms else 0)
        for label, (n, ms) in sorted(per_page.items(), key=lambda kv: kv[1][1], reverse=True)
    ]
    return VisitReport(
        total=format_duration(total_ms),
        page_views=len(views),
        unique_pages=len(per_page),
        avg_per_page=format_duration(total_ms / len(views) if views else 0),
        entry=journey[0].label if journey else "—",
        exit=journey[-1].label if journey else "—",
        journey=journey,
        pages=pages,
    )


def flow_text(session: VisitSession, titles: dict[str, str]) -> str:
    return f" {flow_arrow()} ".join(f"{s.label} {s.duration}" for s in flow(session, titles))


def sessions_with_totals():
    return VisitSession.objects.annotate(
        page_count=Count("views"),
        total_ms=Sum("views__duration_ms"),
    )


@dataclass(frozen=True)
class Summary:
    visitors: int
    visits: int
    page_views: int
    avg_visit: str
    pages_per_visit: str


def summary(since: datetime) -> Summary:
    sessions = sessions_with_totals().filter(started_at__gte=since)
    agg = sessions.aggregate(
        visitors=Count("visitor_id", distinct=True),
        visits=Count("id"),
        avg_ms=Avg("total_ms"),
        avg_pages=Avg("page_count"),
    )
    views = PageView.objects.filter(session__started_at__gte=since).count()
    return Summary(
        visitors=agg["visitors"] or 0,
        visits=agg["visits"] or 0,
        page_views=views,
        avg_visit=format_duration(agg["avg_ms"]),
        pages_per_visit=f"{agg['avg_pages'] or 0:.1f}",
    )


@dataclass(frozen=True)
class PageStat:
    label: str
    path: str
    views: int
    avg_time: str


def top_pages(since: datetime, limit: int = 8) -> list[PageStat]:
    """Most-viewed pages, both languages counted together."""
    titles = page_titles()
    totals: dict[str, list[int]] = {}
    for path, views, avg in (
        PageView.objects.filter(entered_at__gte=since)
        .values("path")
        .annotate(views=Count("id"), avg=Avg("duration_ms"))
        .values_list("path", "views", "avg")
    ):
        key = normalise_path(path)
        count, weighted = totals.get(key, [0, 0])
        totals[key] = [count + views, weighted + (avg or 0) * views]
    ranked = sorted(totals.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    return [
        PageStat(titles.get(path, path), path, count, format_duration(weighted / count if count else 0))
        for path, (count, weighted) in ranked
    ]


def daily_visits(days: int = 14) -> tuple[list[str], list[int]]:
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    counts = dict(
        VisitSession.objects.filter(started_at__date__gte=start)
        .annotate(day=TruncDate("started_at"))
        .values("day")
        .annotate(n=Count("id"))
        .values_list("day", "n")
    )
    labels, values = [], []
    for i in range(days):
        day: date = start + timedelta(days=i)
        labels.append(date_format(day, "j M"))  # localised month names
        values.append(counts.get(day, 0))
    return labels, values


def recent_visits(limit: int = 8):
    return sessions_with_totals().prefetch_related("views").order_by("-started_at")[:limit]


def devices(since: datetime) -> dict[str, int]:
    return dict(
        VisitSession.objects.filter(started_at__gte=since)
        .values("device")
        .annotate(n=Count("id"))
        .values_list("device", "n")
    )


def languages(since: datetime) -> dict[str, int]:
    return dict(
        VisitSession.objects.filter(started_at__gte=since)
        .exclude(Q(language=""))
        .values("language")
        .annotate(n=Count("id"))
        .values_list("language", "n")
    )
