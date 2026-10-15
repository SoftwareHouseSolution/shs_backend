"""The "Visit analysis" admin page: a full report on the visits in a period.

One pass over the period's sessions and one over their page views (both streamed) gives
every table on the page; the previous period of the same length is summarised the same
way, so each headline figure carries its change. Paths are grouped as on the dashboard:
both languages of a page count as one ("/en/customers" and "/ar/customers" → Our Clients).
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.db.models import Min
from django.utils import timezone
from django.utils.formats import date_format, get_format
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from . import reports
from .models import PageView, VisitSession

# ── Period ──────────────────────────────────────────────────────────────────────────

PRESETS = [
    ("today", gettext_lazy("Today")),
    ("7d", gettext_lazy("Last 7 days")),
    ("30d", gettext_lazy("Last 30 days")),
    ("90d", gettext_lazy("Last 90 days")),
    ("month", gettext_lazy("This month")),
    ("year", gettext_lazy("This year")),
    ("all", gettext_lazy("All time")),
]
DEFAULT_PRESET = "30d"


@dataclass(frozen=True)
class Period:
    key: str  # a preset key, or "custom"
    first: date | None  # None: from the first recorded visit
    last: date

    @property
    def start(self) -> datetime | None:
        return timezone.make_aware(datetime.combine(self.first, time.min)) if self.first else None

    @property
    def end(self) -> datetime:
        return timezone.make_aware(datetime.combine(self.last + timedelta(days=1), time.min))

    def previous(self) -> "Period | None":
        """The same number of days just before this period — nothing to compare "all time" to."""
        if self.first is None:
            return None
        days = (self.last - self.first).days + 1
        return Period("previous", self.first - timedelta(days=days), self.first - timedelta(days=1))

    @property
    def label(self) -> str:
        if self.first is None:
            return str(_("All time"))
        if self.first == self.last:
            return date_format(self.first, "j F Y")
        return f"{date_format(self.first, 'j M Y')} – {date_format(self.last, 'j M Y')}"


def period_from(params) -> Period:
    """The period a request asks for: ?range=<preset>, or ?from=YYYY-MM-DD&to=YYYY-MM-DD."""
    today = timezone.localdate()
    first, last = _parse_date(params.get("from")), _parse_date(params.get("to"))
    if first or last:
        first, last = first or last, min(last or today, today)
        if first > last:
            first, last = last, first
        return Period("custom", first, last)
    key = params.get("range") if params.get("range") in dict(PRESETS) else DEFAULT_PRESET
    starts = {
        "today": today,
        "7d": today - timedelta(days=6),
        "30d": today - timedelta(days=29),
        "90d": today - timedelta(days=89),
        "month": today.replace(day=1),
        "year": today.replace(month=1, day=1),
        "all": None,
    }
    return Period(key, starts[key], today)


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


# ── Report ──────────────────────────────────────────────────────────────────────────


@dataclass
class Kpi:
    key: str
    title: str
    icon: str
    value: str
    raw: float
    change: int | None = None  # % against the previous period
    good_when_up: bool = True

    @property
    def trend(self) -> str:
        if self.change is None or self.change == 0:
            return "flat"
        return "good" if (self.change > 0) == self.good_when_up else "bad"


@dataclass
class Row:
    """A ranked line in a breakdown table."""

    label: str
    count: int
    pct: int = 0  # share of the total
    bar: int = 0  # of the largest row, for the bar
    extra: dict = field(default_factory=dict)


@dataclass
class Analysis:
    period: Period
    previous: Period | None
    has_data: bool
    kpis: list[Kpi]
    trend_chart: str
    trend_unit: str
    pages: list[Row]
    entries: list[Row]
    exits: list[Row]
    transitions: list[Row]
    sources: list[Row]
    devices: list[Row]
    browsers: list[Row]
    systems: list[Row]
    languages: list[Row]
    new_vs_returning: list[Row]
    lengths: list[Row]
    depths: list[Row]
    heatmap: dict
    insights: list[dict]
    series: list[tuple[str, int, int, int]]  # bucket label, visits, visitors, page views — for CSV


def analyse(period: Period) -> Analysis:
    sessions = _sessions(period)
    views = _views(period, sessions)

    previous = period.previous()
    prev_sessions = _sessions(previous) if previous else {}
    first_seen = _first_seen({s["visitor_id"] for s in (*sessions.values(), *prev_sessions.values())})
    prev = _totals(prev_sessions, first_seen) if previous else None

    totals = _totals(sessions, first_seen)
    pages, entries, exits, transitions = _page_tables(sessions, views)
    labels, series = _series(period, sessions, views)
    return Analysis(
        period=period,
        previous=previous,
        has_data=bool(sessions),
        kpis=_kpis(totals, prev),
        trend_chart=_trend_chart(labels, series),
        trend_unit=_("per month") if _monthly(period, sessions) else _("per day"),
        pages=pages,
        entries=entries,
        exits=exits,
        transitions=transitions,
        sources=_sources(sessions),
        devices=_ranked(Counter(s["device"] for s in sessions.values()), _device_labels(), _device_icons()),
        browsers=_ranked(Counter(s["browser"] or _("Unknown") for s in sessions.values()), limit=6),
        systems=_ranked(Counter(s["os"] or _("Unknown") for s in sessions.values()), limit=6),
        languages=_ranked(
            Counter(s["language"] or "—" for s in sessions.values()), {"en": _("English"), "ar": _("Arabic")}
        ),
        new_vs_returning=_new_vs_returning(sessions, first_seen),
        lengths=_lengths(sessions),
        depths=_depths(sessions),
        heatmap=_heatmap(sessions),
        insights=_insights(sessions, pages, exits),
        series=[(label, *values) for label, values in zip(labels, series, strict=True)],
    )


# ── Data ────────────────────────────────────────────────────────────────────────────


def _sessions(period: Period) -> dict[int, dict]:
    qs = reports.sessions_with_totals().filter(started_at__lt=period.end)
    if period.start:
        qs = qs.filter(started_at__gte=period.start)
    fields = ["id", "visitor_id", "started_at", "device", "browser", "os", "language", "referrer_host", "page_count", "total_ms"]
    return {s["id"]: s for s in qs.values(*fields).iterator()}


def _views(period: Period, sessions: dict[int, dict]) -> dict[int, list[tuple[str, int]]]:
    """Each session's views in order, as (normalised path, ms)."""
    qs = PageView.objects.filter(session__started_at__lt=period.end)
    if period.start:
        qs = qs.filter(session__started_at__gte=period.start)
    by_session: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for sid, path, ms in qs.order_by("session_id", "sequence", "entered_at").values_list("session_id", "path", "duration_ms").iterator():
        if sid in sessions:
            by_session[sid].append((reports.normalise_path(path), ms))
    return by_session


def _first_seen(visitor_ids: set) -> dict:
    if not visitor_ids:
        return {}
    return dict(
        VisitSession.objects.filter(visitor_id__in=visitor_ids)
        .values("visitor_id")
        .annotate(first=Min("started_at"))
        .values_list("visitor_id", "first")
    )


@dataclass(frozen=True)
class _Totals:
    visits: int
    visitors: int
    page_views: int
    total_ms: int
    bounces: int
    returning: int

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.visits if self.visits else 0

    @property
    def pages_per_visit(self) -> float:
        return self.page_views / self.visits if self.visits else 0

    @property
    def bounce_rate(self) -> float:
        return 100 * self.bounces / self.visits if self.visits else 0

    @property
    def returning_rate(self) -> float:
        return 100 * self.returning / self.visits if self.visits else 0


def _is_returning(session: dict, first_seen: dict) -> bool:
    """A visit from a browser that had visited before (at any time, not only in the period)."""
    return session["started_at"] > first_seen.get(session["visitor_id"], session["started_at"])


def _totals(sessions: dict[int, dict], first_seen: dict) -> _Totals:
    counts = [s["page_count"] or 0 for s in sessions.values()]
    return _Totals(
        visits=len(sessions),
        visitors=len({s["visitor_id"] for s in sessions.values()}),
        page_views=sum(counts),
        total_ms=sum(s["total_ms"] or 0 for s in sessions.values()),
        bounces=sum(1 for n in counts if n <= 1),
        returning=sum(1 for s in sessions.values() if _is_returning(s, first_seen)),
    )


# ── Sections ────────────────────────────────────────────────────────────────────────


def _change(now: float, before: float | None) -> int | None:
    if before is None or before == 0:
        return None
    return round(100 * (now - before) / before)


def _kpis(t: _Totals, prev: _Totals | None) -> list[Kpi]:
    def k(key, title, icon, value, raw, before, good_when_up=True):
        return Kpi(key, title, icon, value, raw, _change(raw, before) if prev else None, good_when_up)

    p = prev or t  # only read when prev exists
    return [
        k("visitors", _("Visitors"), "group", f"{t.visitors:,}", t.visitors, p.visitors),
        k("visits", _("Visits"), "login", f"{t.visits:,}", t.visits, p.visits),
        k("views", _("Page views"), "visibility", f"{t.page_views:,}", t.page_views, p.page_views),
        k("duration", _("Avg. visit duration"), "schedule", reports.format_duration(t.avg_ms), t.avg_ms, p.avg_ms),
        k("depth", _("Pages per visit"), "layers", f"{t.pages_per_visit:.1f}", t.pages_per_visit, p.pages_per_visit),
        k("bounce", _("Bounce rate"), "keyboard_return", f"{t.bounce_rate:.0f}%", t.bounce_rate, p.bounce_rate, False),
        k("returning", _("Returning visits"), "replay", f"{t.returning_rate:.0f}%", t.returning_rate, p.returning_rate),
        k("time", _("Total time on site"), "hourglass_top", reports.format_duration(t.total_ms), t.total_ms, p.total_ms),
    ]


def _ranked(counter: Counter, labels: dict | None = None, icons: dict | None = None, *, limit: int | None = None) -> list[Row]:
    total = sum(counter.values())
    items = counter.most_common(limit)
    top = items[0][1] if items else 0
    return [
        Row(
            (labels or {}).get(key, key),
            n,
            round(100 * n / total) if total else 0,
            round(100 * n / top) if top else 0,
            {"icon": (icons or {}).get(key, "")},
        )
        for key, n in items
    ]


def _device_labels() -> dict:
    return dict(VisitSession.Device.choices)


def _device_icons() -> dict:
    return {"desktop": "computer", "tablet": "tablet_mac", "mobile": "smartphone"}


def _page_tables(sessions, views):
    titles = reports.page_titles()
    stats: dict[str, dict] = defaultdict(lambda: {"views": 0, "ms": 0, "visits": set(), "entries": 0, "exits": 0, "bounces": 0})
    moves: Counter = Counter()
    for sid, steps in views.items():
        for i, (path, ms) in enumerate(steps):
            s = stats[path]
            s["views"] += 1
            s["ms"] += ms
            s["visits"].add(sid)
            if i and steps[i - 1][0] != path:
                moves[(steps[i - 1][0], path)] += 1
        if steps:
            stats[steps[0][0]]["entries"] += 1
            stats[steps[-1][0]]["exits"] += 1
            if len(steps) == 1:
                stats[steps[0][0]]["bounces"] += 1

    total_views = sum(s["views"] for s in stats.values())
    ranked = sorted(stats.items(), key=lambda kv: kv[1]["views"], reverse=True)
    top_views = ranked[0][1]["views"] if ranked else 0

    def label(path):
        return titles.get(path, path)

    pages = [
        Row(
            label(path),
            s["views"],
            round(100 * s["views"] / total_views) if total_views else 0,
            round(100 * s["views"] / top_views) if top_views else 0,
            {
                "path": path,
                "visits": len(s["visits"]),
                "avg_ms": s["ms"] / s["views"],
                "avg_time": reports.format_duration(s["ms"] / s["views"]),
                "total_time": reports.format_duration(s["ms"]),
                "entries": s["entries"],
                "exit_rate": round(100 * s["exits"] / s["views"]),
            },
        )
        for path, s in ranked[:20]
    ]
    visits = len(views)

    def side(key: str, rate_of: str) -> list[Row]:
        items = sorted(((p, s) for p, s in stats.items() if s[key]), key=lambda kv: kv[1][key], reverse=True)[:8]
        top = items[0][1][key] if items else 0
        return [
            Row(
                label(p),
                s[key],
                round(100 * s[key] / visits) if visits else 0,
                round(100 * s[key] / top) if top else 0,
                {"path": p, "rate": round(100 * s[rate_of] / (s["entries"] if key == "entries" else s["views"]))},
            )
            for p, s in items
        ]

    entries = side("entries", "bounces")  # rate: of the visits that started here, how many left at once
    exits = side("exits", "exits")  # rate: of the views of this page, how many ended the visit
    top_move = moves.most_common(1)[0][1] if moves else 0
    transitions = [
        Row(f"{label(a)} {reports.flow_arrow()} {label(b)}", n, 0, round(100 * n / top_move) if top_move else 0)
        for (a, b), n in moves.most_common(10)
    ]
    return pages, entries, exits, transitions


def _sources(sessions) -> list[Row]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in sessions.values():
        groups[s["referrer_host"] or ""].append(s)
    total = len(sessions)
    ranked = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)[:10]
    top = len(ranked[0][1]) if ranked else 0
    rows = []
    for host, group in ranked:
        views = sum(s["page_count"] or 0 for s in group)
        ms = sum(s["total_ms"] or 0 for s in group)
        rows.append(
            Row(
                host or _("Direct / unknown"),
                len(group),
                round(100 * len(group) / total) if total else 0,
                round(100 * len(group) / top) if top else 0,
                {
                    "icon": "link" if host else "keyboard",
                    "ltr": bool(host),
                    "pages_per_visit": f"{views / len(group):.1f}",
                    "avg_time": reports.format_duration(ms / len(group)),
                },
            )
        )
    return rows


def _new_vs_returning(sessions, first_seen) -> list[Row]:
    counter = Counter("returning" if _is_returning(s, first_seen) else "new" for s in sessions.values())
    return _ranked(counter, {"new": _("New visits"), "returning": _("Returning visits")}, {"new": "person_add", "returning": "replay"})


# Upper bounds (exclusive) of the distribution buckets; the last bucket is open-ended.
LENGTH_BOUNDS = [10, 30, 60, 180, 600, 1800]  # seconds
DEPTH_BOUNDS = [2, 3, 5, 10, 20]  # pages


def _seconds_label(seconds: int) -> str:
    return _("%(s)ds") % {"s": seconds} if seconds < 60 else _("%(m)dm") % {"m": seconds // 60}


def _distribution(values, bounds: list[int], label) -> list[Row]:
    counts = [0] * (len(bounds) + 1)
    for v in values:
        counts[next((i for i, upper in enumerate(bounds) if v < upper), len(bounds))] += 1
    total, top = sum(counts), max(counts)
    lows = [0, *bounds]
    labels = [label(lo, hi) for lo, hi in zip(lows, bounds, strict=False)] + [label(bounds[-1], None)]
    return [
        Row(text, n, round(100 * n / total) if total else 0, round(100 * n / top) if top else 0)
        for text, n in zip(labels, counts, strict=True)
    ]


def _lengths(sessions) -> list[Row]:
    def label(lo, hi):
        return f"{_seconds_label(lo)}+" if hi is None else f"{_seconds_label(lo)}–{_seconds_label(hi)}"

    return _distribution(((s["total_ms"] or 0) / 1000 for s in sessions.values()), LENGTH_BOUNDS, label)


def _depths(sessions) -> list[Row]:
    def label(lo, hi):
        lo = max(lo, 1)
        if hi is None:
            return f"{lo}+"
        return str(lo) if hi - lo == 1 else f"{lo}–{hi - 1}"

    return _distribution((s["page_count"] or 0 for s in sessions.values()), DEPTH_BOUNDS, label)


def _heatmap(sessions) -> dict:
    """Visits by weekday × hour, weekdays from the locale's first day of the week."""
    grid = [[0] * 24 for _ in range(7)]  # Python weekday: Monday = 0
    for s in sessions.values():
        local = timezone.localtime(s["started_at"])
        grid[local.weekday()][local.hour] += 1
    first = int(get_format("FIRST_DAY_OF_WEEK"))  # 0 = Sunday … 6 = Saturday
    order = [(first - 1 + i) % 7 for i in range(7)]  # → Python weekdays
    top = max((max(row) for row in grid), default=0)
    monday = date(2024, 1, 1)  # a Monday, for localised day names
    rows = [
        {
            "day": date_format(monday + timedelta(days=wd), "D"),
            "cells": [{"n": n, "level": round(100 * n / top) if top else 0, "hour": h} for h, n in enumerate(grid[wd])],
            "total": sum(grid[wd]),
        }
        for wd in order
    ]
    hours = [sum(grid[wd][h] for wd in range(7)) for h in range(24)]
    return {"rows": rows, "hours": list(range(24)), "peak_hour": hours.index(max(hours)) if top else None}


def _monthly(period: Period, sessions) -> bool:
    first = period.first or min((timezone.localtime(s["started_at"]).date() for s in sessions.values()), default=period.last)
    return (period.last - first).days > 92


def _series(period: Period, sessions, views) -> tuple[list[str], list[tuple[int, int, int]]]:
    """Visits, visitors and page views per day — per month for periods over three months."""
    first = period.first or min((timezone.localtime(s["started_at"]).date() for s in sessions.values()), default=period.last)
    monthly = _monthly(period, sessions)

    def key(d: date) -> date:
        return d.replace(day=1) if monthly else d

    buckets: list[date] = []
    d = key(first)
    while d <= period.last:
        buckets.append(d)
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1) if monthly else d + timedelta(days=1)

    visits: Counter = Counter()
    visitors: dict[date, set] = defaultdict(set)
    page_views: Counter = Counter()
    for s in sessions.values():
        b = key(timezone.localtime(s["started_at"]).date())
        visits[b] += 1
        visitors[b].add(s["visitor_id"])
        page_views[b] += s["page_count"] or 0
    labels = [date_format(b, "M Y" if monthly else "j M") for b in buckets]
    return labels, [(visits[b], len(visitors[b]), page_views[b]) for b in buckets]


def _trend_chart(labels, series) -> str:
    import json

    def line(label, values, color, fill):
        return {
            "label": str(label),
            "data": values,
            "borderColor": color,
            "backgroundColor": fill,
            "fill": fill != "transparent",
            "tension": 0.35,
            "pointRadius": 0 if len(values) > 31 else 3,
            "pointHoverRadius": 5,
            "pointBackgroundColor": color,
        }

    # Chart.js draws the first dataset on top, so Visitors comes before the filled Visits.
    # Page views are left out: an order of magnitude larger, they would flatten both lines.
    return json.dumps(
        {
            "labels": labels,
            "datasets": [
                line(_("Visitors"), [v[1] for v in series], "#0d9488", "transparent"),
                line(_("Visits"), [v[0] for v in series], "var(--color-primary-600)", "rgba(74, 111, 166, 0.12)"),
            ],
        }
    )


def _insights(sessions, pages: list[Row], exits: list[Row]) -> list[dict]:
    """A few plain-language findings, each only when there is enough data to say it."""
    if len(sessions) < 3:
        return []
    out = []
    days = Counter(timezone.localtime(s["started_at"]).date() for s in sessions.values())
    best_day, n = days.most_common(1)[0]
    out.append({"icon": "trending_up", "text": _("Busiest day: %(day)s, with %(n)d visits.") % {"day": date_format(best_day, "l j F"), "n": n}})

    weekdays = Counter(timezone.localtime(s["started_at"]).weekday() for s in sessions.values())
    wd = weekdays.most_common(1)[0][0]
    out.append({"icon": "event", "text": _("%(day)s is the strongest day of the week.") % {"day": date_format(date(2024, 1, 1) + timedelta(days=wd), "l")}})

    hours = Counter(timezone.localtime(s["started_at"]).hour for s in sessions.values())
    h = hours.most_common(1)[0][0]
    out.append({"icon": "schedule", "text": _("Most visits start between %(a)02d:00 and %(b)02d:00.") % {"a": h, "b": (h + 1) % 24}})

    engaging = [p for p in pages if p.count >= 3]
    if engaging:
        best = max(engaging, key=lambda p: p.extra["avg_ms"])
        out.append({"icon": "visibility", "text": _("“%(page)s” holds attention longest: %(t)s per view on average.") % {"page": best.label, "t": best.extra["avg_time"]}})
    leaky = [e for e in exits if e.count >= 3]
    if leaky:
        worst = max(leaky, key=lambda e: e.extra["rate"])
        out.append({"icon": "logout", "text": _("%(rate)d%% of views of “%(page)s” end the visit — the highest exit rate.") % {"rate": worst.extra["rate"], "page": worst.label}})
    return out

