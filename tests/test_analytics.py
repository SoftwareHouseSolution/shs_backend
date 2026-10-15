import json
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.analytics import reports
from apps.analytics.models import PageView, VisitSession
from apps.analytics.services import MAX_VIEW_DURATION_MS, AnalyticsService, ViewReport
from apps.analytics.user_agents import classify
from apps.core.codes import ResponseCode
from tests.contract import assert_envelope

pytestmark = pytest.mark.django_db

URL = "/api/v1/analytics/collect/"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"


def report(session, visitor, path="/en", duration=0, view=None):
    return {
        "session_id": str(session),
        "visitor_id": str(visitor),
        "view_id": str(view or uuid.uuid4()),
        "path": path,
        "language": "en",
        "duration_ms": duration,
    }


# ── User agents ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("ua", "device", "browser", "os"),
    [
        (CHROME, "desktop", "Chrome", "Windows"),
        (IPHONE, "mobile", "Safari", "iOS"),
        ("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) Safari/604.1", "tablet", "Safari", "iOS"),
        ("Mozilla/5.0 (Linux; Android 14; SM-S918B) Chrome/141.0 Mobile Safari/537.36 SamsungBrowser/26.0", "mobile", "Samsung Internet", "Android"),
        ("Mozilla/5.0 (Windows NT 10.0) Chrome/141.0 Safari/537.36 Edg/141.0", "desktop", "Edge", "Windows"),
    ],
)
def test_user_agent_classification(ua, device, browser, os):
    c = classify(ua)
    assert (c.is_bot, c.device, c.browser, c.os) == (False, device, browser, os)


@pytest.mark.parametrize("ua", ["Googlebot/2.1", "HeadlessChrome/141.0", "curl/8.4", "", "python-requests/2.32"])
def test_bots_and_scripts_are_recognised(ua):
    assert classify(ua).is_bot


# ── Service ──────────────────────────────────────────────────────────────────────────


def test_a_visit_is_recorded_as_an_ordered_flow_with_durations():
    service = AnalyticsService()
    s, v = uuid.uuid4(), uuid.uuid4()
    home, customers = uuid.uuid4(), uuid.uuid4()
    service.record(ViewReport(s, v, home, "/en", "en", "https://www.google.com/search"), user_agent=CHROME)
    service.record(ViewReport(s, v, home, "/en", "en", duration_ms=4200), user_agent=CHROME)
    service.record(ViewReport(s, v, customers, "/en/customers", "en", duration_ms=0), user_agent=CHROME)
    service.record(ViewReport(s, v, customers, "/en/customers", "en", duration_ms=7100), user_agent=CHROME)

    session = VisitSession.objects.get(session_id=s)
    assert session.landing_path == "/en" and session.referrer_host == "www.google.com"
    assert session.device == "desktop" and session.browser == "Chrome"
    assert reports.flow_text(session, reports.page_titles()) == "Home 4s → Our Clients 7s"


def test_duration_only_grows_so_late_or_duplicate_reports_are_harmless():
    service = AnalyticsService()
    s, v, view = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    for ms in (0, 9000, 3000, 9000):
        service.record(ViewReport(s, v, view, "/en/our-team", duration_ms=ms), user_agent=CHROME)
    assert PageView.objects.get(view_id=view).duration_ms == 9000
    assert PageView.objects.count() == 1


def test_duration_is_capped():
    service = AnalyticsService()
    service.record(ViewReport(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "/en", duration_ms=10**9), user_agent=CHROME)
    assert PageView.objects.get().duration_ms == MAX_VIEW_DURATION_MS


def test_bots_are_not_recorded():
    assert AnalyticsService().record(ViewReport(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "/en"), user_agent="Googlebot") is False
    assert VisitSession.objects.count() == 0


def test_internal_referrer_is_not_a_source():
    s = uuid.uuid4()
    AnalyticsService().record(
        ViewReport(s, uuid.uuid4(), uuid.uuid4(), "/en", referrer="https://www.example.com/ar"),
        user_agent=CHROME,
        site_host="www.example.com",
    )
    assert VisitSession.objects.get(session_id=s).referrer_host == ""


# ── API ──────────────────────────────────────────────────────────────────────────────


def test_collect_accepts_json_with_202_envelope(api):
    s, v = uuid.uuid4(), uuid.uuid4()
    body = assert_envelope(
        api.post(URL, report(s, v), format="json", HTTP_USER_AGENT=CHROME),
        status=202,
        code=ResponseCode.ANALYTICS_EVENT_ACCEPTED,
    )
    assert body["data"] is None
    assert VisitSession.objects.filter(session_id=s).exists()


def test_collect_accepts_beacon_text_plain(api):
    s = uuid.uuid4()
    response = api.post(URL, json.dumps(report(s, uuid.uuid4())), content_type="text/plain;charset=UTF-8", HTTP_USER_AGENT=IPHONE)
    assert_envelope(response, status=202, code=ResponseCode.ANALYTICS_EVENT_ACCEPTED)
    assert VisitSession.objects.get(session_id=s).device == "mobile"


def test_bot_reports_get_the_same_answer_but_are_dropped(api):
    response = api.post(URL, report(uuid.uuid4(), uuid.uuid4()), format="json", HTTP_USER_AGENT="AhrefsBot/7.0")
    assert_envelope(response, status=202, code=ResponseCode.ANALYTICS_EVENT_ACCEPTED)
    assert VisitSession.objects.count() == 0


def test_query_strings_are_stripped_from_paths(api):
    api.post(URL, report(uuid.uuid4(), uuid.uuid4(), path="/en/customers?email=a@b.co#x"), format="json", HTTP_USER_AGENT=CHROME)
    assert PageView.objects.get().path == "/en/customers"


@pytest.mark.parametrize(
    ("override", "field"),
    [({"path": "https://evil.example/x"}, "path"), ({"session_id": "nope"}, "session_id"), ({"duration_ms": -5}, "duration_ms"), ({"language": "fr"}, "language")],
)
def test_invalid_reports_are_validation_errors(api, override, field):
    payload = {**report(uuid.uuid4(), uuid.uuid4()), **override}
    body = assert_envelope(api.post(URL, payload, format="json", HTTP_USER_AGENT=CHROME), status=400, code=ResponseCode.VALIDATION_ERROR)
    assert field in body["errors"]


def test_collect_is_rate_limited(api, monkeypatch):
    from rest_framework.throttling import SimpleRateThrottle

    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", {"anon": "1000/min", "analytics": "2/min"})
    for _ in range(2):
        api.post(URL, report(uuid.uuid4(), uuid.uuid4()), format="json", HTTP_USER_AGENT=CHROME)
    response = api.post(URL, report(uuid.uuid4(), uuid.uuid4()), format="json", HTTP_USER_AGENT=CHROME)
    assert_envelope(response, status=429, code=ResponseCode.RATE_LIMIT_EXCEEDED)


# ── Reports, admin, retention ────────────────────────────────────────────────────────


def _visit(paths_ms, *, days_ago=0, visitor=None, ua=CHROME):
    service = AnalyticsService(clock=lambda: timezone.now() - timedelta(days=days_ago))
    s, v = uuid.uuid4(), visitor or uuid.uuid4()
    for path, ms in paths_ms:
        service.record(ViewReport(s, v, uuid.uuid4(), path, "en", duration_ms=ms), user_agent=ua)
    return VisitSession.objects.get(session_id=s)


def test_reports_summary_top_pages_and_daily_counts():
    visitor = uuid.uuid4()
    _visit([("/en", 4000), ("/en/customers", 7000)], visitor=visitor)
    _visit([("/ar", 2000), ("/ar/customers/", 3000), ("/ar/our-team", 10000)], visitor=visitor)
    _visit([("/en", 1000)], days_ago=20)  # outside the 7-day window

    since = timezone.now() - timedelta(days=7)
    s = reports.summary(since)
    assert (s.visitors, s.visits, s.page_views) == (1, 2, 5)
    assert s.avg_visit == "13s" and s.pages_per_visit == "2.5"

    top = {p.label: p for p in reports.top_pages(since)}
    assert top["Home"].views == 2 and top["Our Clients"].views == 2  # both languages together
    assert top["Our Clients"].avg_time == "5s"

    labels, values = reports.daily_visits(14)
    assert len(labels) == 14 and values[-1] == 2


@pytest.mark.parametrize(("ms", "text"), [(0, "0s"), (4400, "4s"), (65000, "1m 05s"), (3_725_000, "1h 02m")])
def test_duration_formatting(ms, text):
    assert reports.format_duration(ms) == text


def test_admin_dashboard_and_visit_pages_show_the_flow(admin_client):
    session = _visit([("/en", 4000), ("/en/customers", 7000), ("/en/about-company", 12000)])
    dashboard = admin_client.get(reverse("admin:index")).content.decode()
    assert "Latest visits" in dashboard and "Our Clients" in dashboard

    listing = admin_client.get(reverse("admin:analytics_visitsession_changelist")).content.decode()
    assert "About Company" in listing and "12s" in listing

    detail = admin_client.get(reverse("admin:analytics_visitsession_change", args=[session.pk]))
    body = detail.content.decode()
    assert detail.status_code == 200 and "Path through the site" in body and "/en/about-company" in body
    assert admin_client.get(reverse("admin:analytics_pageview_changelist")).status_code == 200


def test_visit_report_groups_repeats_and_splits_time_by_page():
    session = _visit([("/en", 2000), ("/en", 3000), ("/en/customers", 15000), ("/en", 5000)])
    report = reports.visit_report(session, reports.page_titles())

    assert [(s.label, s.views, s.duration) for s in report.journey] == [
        ("Home", 2, "5s"),
        ("Our Clients", 1, "15s"),
        ("Home", 1, "5s"),
    ]
    assert [(p.label, p.views, p.pct) for p in report.pages] == [("Our Clients", 1, 60), ("Home", 3, 40)]
    assert (report.page_views, report.unique_pages, report.entry, report.exit) == (4, 2, "Home", "Home")
    assert report.total == "25s" and report.avg_per_page == "6s"


def test_visit_page_lists_the_visitors_other_visits(admin_client):
    visitor = uuid.uuid4()
    first = _visit([("/en", 1000)], days_ago=1, visitor=visitor)
    second = _visit([("/en/customers", 2000)], visitor=visitor)
    body = admin_client.get(reverse("admin:analytics_visitsession_change", args=[second.pk])).content.decode()
    assert "Returning visitor" in body and "Other visits by this visitor" in body
    assert reverse("admin:analytics_visitsession_change", args=[first.pk]) in body


def test_analysis_period_from_presets_and_dates():
    from apps.analytics.analysis import period_from

    today = timezone.localdate()
    assert period_from({}).first == today - timedelta(days=29)  # default: last 30 days
    week = period_from({"range": "7d"})
    assert (week.first, week.last) == (today - timedelta(days=6), today)
    assert week.previous().last == today - timedelta(days=7) and week.previous().first == today - timedelta(days=13)
    assert period_from({"range": "all"}).first is None and period_from({"range": "all"}).previous() is None
    custom = period_from({"from": "2026-02-10", "to": "2026-02-01"})  # reversed dates are swapped
    assert (custom.key, str(custom.first), str(custom.last)) == ("custom", "2026-02-01", "2026-02-10")
    assert period_from({"from": "not-a-date", "range": "nope"}).key == "30d"


def test_analysis_figures_and_tables():
    from apps.analytics.analysis import analyse, period_from

    visitor = uuid.uuid4()
    _visit([("/en", 30_000)], days_ago=10, visitor=visitor)  # previous period
    _visit([("/en", 4000), ("/en/customers", 6000)], visitor=visitor)  # returning
    _visit([("/ar/customers", 20_000)])  # bounce, new
    report = analyse(period_from({"range": "7d"}))

    kpis = {k.key: k for k in report.kpis}
    assert (kpis["visitors"].value, kpis["visits"].value, kpis["views"].value) == ("2", "2", "3")
    assert kpis["bounce"].value == "50%" and kpis["returning"].value == "50%"
    assert kpis["visits"].change == 100 and kpis["duration"].change == -50
    assert kpis["bounce"].change == -50 and kpis["bounce"].trend == "good"  # 100% → 50%: down is good

    pages = {p.label: p for p in report.pages}
    assert pages["Our Clients"].count == 2 and pages["Our Clients"].extra["exit_rate"] == 100  # both languages
    assert [e.label for e in report.entries] == ["Home", "Our Clients"]
    assert [t.label for t in report.transitions] == ["Home → Our Clients"]
    assert sum(r.count for r in report.lengths) == 2 and sum(r.count for r in report.depths) == 2
    assert sum(row["total"] for row in report.heatmap["rows"]) == 2


def test_analysis_page_and_csv_export(admin_client):
    _visit([("/en", 4000), ("/en/customers", 7000)])
    url = reverse("admin:analytics_visitsession_analysis")
    for params in ({}, {"range": "all"}, {"range": "today"}, {"from": "2020-01-01", "to": "2020-01-31"}):
        assert admin_client.get(url, params).status_code == 200
    page = admin_client.get(url).content.decode()
    assert "Visit analysis" in page and "Our Clients" in page and "Traffic sources" in page

    export = admin_client.get(url, {"range": "7d", "export": "csv"})
    assert export["Content-Type"].startswith("text/csv") and "attachment" in export["Content-Disposition"]
    body = export.content.decode("utf-8-sig")
    assert "Our Clients" in body and "/customers" in body


def test_analysis_page_needs_view_permission(client):
    from django.contrib.auth.models import User

    staff = User.objects.create_user("editor", password="x", is_staff=True)
    client.force_login(staff)
    assert client.get(reverse("admin:analytics_visitsession_analysis")).status_code == 403


def test_analytics_admin_is_read_only(admin_client):
    assert admin_client.get(reverse("admin:analytics_visitsession_add")).status_code == 403


def test_prune_removes_old_visits():
    _visit([("/en", 1000)], days_ago=200)
    recent = _visit([("/en", 1000)])
    call_command("prune_analytics", "--days", "180", verbosity=0)
    assert list(VisitSession.objects.values_list("pk", flat=True)) == [recent.pk]
    assert PageView.objects.count() == 1
