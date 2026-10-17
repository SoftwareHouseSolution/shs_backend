"""Admin → System status and `manage.py system_status`."""

import io
import logging

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.content.models import Partner
from apps.core import system_status
from apps.core.system_status import ERROR, Check, RecentErrorsHandler, Section

URL = reverse("admin-system-status")


@pytest.mark.django_db
def test_superusers_see_every_section(admin_client):
    response = admin_client.get(URL)
    assert response.status_code == 200
    titles = [s.title for s in response.context["report"].sections]
    assert titles == ["Application", "Server", "Database", "Cache", "Media files", "Configuration", "Recent errors"]
    assert b"System status" in response.content


@pytest.mark.django_db
def test_editors_are_refused(client, django_user_model):
    client.force_login(django_user_model.objects.create_user("editor", password="x", is_staff=True))
    assert client.get(URL).status_code == 403


def test_signed_out_visitors_are_sent_to_login(client):
    response = client.get(URL)
    assert response.status_code == 302 and "/login/" in response["Location"]


@pytest.mark.django_db
def test_the_report_is_reused_until_refresh(admin_client):
    first = admin_client.get(URL).context["report"]
    assert admin_client.get(URL).context["report"].generated_at == first.generated_at
    assert admin_client.get(URL + "?refresh=1").context["report"].generated_at > first.generated_at


@pytest.mark.django_db
def test_content_pointing_at_a_missing_file_is_a_problem():
    Partner.objects.create(name="Ghost", logo="partners/not-on-disk.svg")
    media = next(s for s in system_status.build_report(use_cache=False).sections if s.key == "media")
    check = next(c for c in media.checks if c.label == "Files used by content")
    assert check.status == ERROR
    assert ["partners/not-on-disk.svg"] in media.tables[0].rows


@pytest.mark.django_db
def test_a_failing_probe_is_reported_without_breaking_the_page(admin_client, monkeypatch):
    def _broken():
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(system_status, "SECTIONS", [*system_status.SECTIONS, _broken])
    response = admin_client.get(URL + "?refresh=1")
    assert response.status_code == 200
    broken = response.context["report"].sections[-1]
    assert broken.status == ERROR and "probe exploded" in broken.checks[0].detail


@pytest.mark.django_db
def test_logged_errors_appear_on_the_page(admin_client):
    record = logging.LogRecord("apps.test", logging.ERROR, __file__, 1, "Payment gateway down\ntrace…", None, None)
    record.request_id = "abc123"
    RecentErrorsHandler().handle(record)
    errors = next(s for s in admin_client.get(URL + "?refresh=1").context["report"].sections if s.key == "errors")
    assert errors.checks[0].value == "1"
    assert errors.tables[0].rows[0][1:] == ["apps.test", "Payment gateway down", "abc123"]


def test_only_errors_are_kept():
    logger = logging.getLogger("tests.recent-errors")
    handler = RecentErrorsHandler()
    logger.addHandler(handler)
    try:
        logger.warning("just a warning")
        logger.error("a real error")
    finally:
        logger.removeHandler(handler)
    assert [e["message"] for e in system_status.recent_errors()] == ["a real error"]


@pytest.mark.django_db
def test_the_command_exits_non_zero_when_a_check_fails(monkeypatch):
    out = io.StringIO()
    call_command("system_status", stdout=out)
    assert "Database" in out.getvalue()

    monkeypatch.setattr(system_status, "SECTIONS", [lambda: Section("x", "X", "error", [Check("Probe", ERROR, "down")])])
    with pytest.raises(SystemExit) as exc:
        call_command("system_status", stdout=io.StringIO())
    assert exc.value.code == 1
