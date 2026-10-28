"""Legal pages: the privacy policy, its on/off switch and its footer link."""

import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.core.codes import ResponseCode
from apps.legal.models import LegalDocument
from tests.contract import assert_envelope

pytestmark = pytest.mark.django_db

URL = "/api/v1/legal/privacy/"


def test_the_privacy_policy_ships_published_in_both_languages(api):
    ar = assert_envelope(api.get(f"{URL}?lang=ar"), status=200, code=ResponseCode.CONTENT_RETRIEVED)["data"]
    en = assert_envelope(api.get(f"{URL}?lang=en"), status=200, code=ResponseCode.CONTENT_RETRIEVED)["data"]
    assert ar["title"] == "سياسة الخصوصية" and en["title"] == "Privacy Policy"
    assert ar["last_updated"] == "2026-10-27"
    assert "## ١. من نحن" in ar["body"] and "## 1. Who we are" in en["body"]
    assert "(/ar#contact)" in ar["body"] and "(/en#contact)" in en["body"]


def test_switching_it_off_takes_the_page_and_the_footer_link_down(api):
    assert api.get("/api/v1/site/").json()["data"]["legal_pages"] == [{"slug": "privacy", "title": "Privacy Policy", "in_footer": True}]
    LegalDocument.objects.update(is_published=False)
    cache.clear()  # a bulk update sends no save signal; the admin's saves do (next test)
    assert_envelope(api.get(URL), status=404, code=ResponseCode.RESOURCE_NOT_FOUND)
    assert api.get("/api/v1/site/").json()["data"]["legal_pages"] == []


def test_the_footer_link_can_be_hidden_while_the_page_stays(api):
    LegalDocument.objects.update(show_in_footer=False)
    assert api.get(URL).status_code == 200
    assert api.get("/api/v1/site/").json()["data"]["legal_pages"] == [{"slug": "privacy", "title": "Privacy Policy", "in_footer": False}]


def test_an_admin_save_refreshes_the_cached_page(api, django_capture_on_commit_callbacks):
    assert api.get(URL).status_code == 200
    doc = LegalDocument.objects.get(slug="privacy")
    doc.is_published = False
    with django_capture_on_commit_callbacks(execute=True):
        doc.save()  # a real save bumps the content cache once it commits
    assert api.get(URL).status_code == 404


def test_unknown_legal_pages_are_404(api):
    assert_envelope(api.get("/api/v1/legal/terms/"), status=404, code=ResponseCode.RESOURCE_NOT_FOUND)


def test_the_admin_lists_and_edits_it(admin_client):
    doc = LegalDocument.objects.get(slug="privacy")
    assert admin_client.get(reverse("admin:legal_legaldocument_changelist")).status_code == 200
    page = admin_client.get(reverse("admin:legal_legaldocument_change", args=[doc.pk]))
    assert page.status_code == 200 and "سياسة الخصوصية".encode() in page.content
