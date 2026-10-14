"""The admin in Arabic: right-to-left, translated, switchable — and isolated from the API."""

import re

import pytest
from django.urls import reverse
from django.utils import translation

from apps.analytics import reports
from apps.site_config.models import SiteSettings

pytestmark = pytest.mark.django_db


def _html_tag(html: str) -> str:
    return re.search(r"<html[^>]*>", html).group(0)


def test_admin_follows_the_browser_language(admin_client):
    ar = admin_client.get(reverse("admin:index"), HTTP_ACCEPT_LANGUAGE="ar").content.decode()
    assert 'dir="rtl"' in _html_tag(ar) and 'lang="ar"' in _html_tag(ar)
    for text in ("لوحة التحكم", "الصفحات", "الزوار", "إعدادات الموقع", "أحدث الزيارات"):
        assert text in ar, text

    en = admin_client.get(reverse("admin:index"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert 'dir="ltr"' in _html_tag(en) and "Latest visits" in en


def test_language_switcher_overrides_the_browser(admin_client):
    response = admin_client.post(reverse("set_language"), {"language": "ar", "next": reverse("admin:index")})
    assert response.status_code == 302
    page = admin_client.get(reverse("admin:index"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert 'dir="rtl"' in _html_tag(page)


def test_admin_language_never_leaks_into_the_api(admin_client):
    admin_client.post(reverse("set_language"), {"language": "ar", "next": "/"})
    response = admin_client.get("/api/v1/site/", HTTP_ACCEPT_LANGUAGE="en")
    assert response["Content-Language"] == "en"
    assert response.json()["message"] == "Content retrieved successfully."


def test_arabic_forms_translate_labels_and_keep_input_directions(admin_client):
    url = reverse("admin:site_config_sitesettings_change", args=[SiteSettings.SINGLETON_PK])
    html = admin_client.get(url, HTTP_ACCEPT_LANGUAGE="ar").content.decode()
    assert "اسم الموقع" in html and "رابط واتساب" in html

    def tag(name):
        return re.search(rf'<(?:input|textarea)[^>]*name="{name}"[^>]*>', html).group(0)

    assert 'dir="rtl"' in tag("site_name_ar")
    assert 'dir="ltr"' in tag("site_name_en")  # English copy stays LTR in an RTL admin
    assert 'dir="ltr"' in tag("whatsapp_url") and 'dir="ltr"' in tag("sales_email")


@pytest.mark.parametrize(("lang", "ms", "text"), [("en", 4000, "4s"), ("ar", 4000, "4 ث"), ("ar", 65000, "1 د 05 ث")])
def test_durations_follow_the_admin_language(lang, ms, text):
    with translation.override(lang):
        assert reports.format_duration(ms) == text


def test_flow_arrow_points_with_the_reading_direction():
    with translation.override("en"):
        assert reports.flow_arrow() == "→"
    with translation.override("ar"):
        assert reports.flow_arrow() == "←"


def test_every_admin_page_renders_in_arabic(admin_client):
    from django.contrib import admin

    for model in admin.site._registry:
        opts = model._meta
        response = admin_client.get(
            reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"), HTTP_ACCEPT_LANGUAGE="ar", follow=True
        )
        assert response.status_code == 200, opts.label


def test_direct_admin_login_lands_on_the_dashboard(client, superuser):
    response = client.post(reverse("admin:login"), {"username": "admin-test", "password": "x" * 12})
    assert response.status_code == 302 and response["Location"] == reverse("admin:index")
