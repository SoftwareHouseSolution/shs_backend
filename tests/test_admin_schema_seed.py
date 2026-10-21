import json
import re

import pytest
import yaml
from django.contrib import admin
from django.core.management import call_command
from django.urls import reverse

from apps.clients.models import Client
from apps.core.admin_utils import missing_arabic
from apps.pages.models import Page, PageBlock
from apps.site_config.models import NavigationItem, SiteSettings

pytestmark = pytest.mark.django_db


# ── Admin ────────────────────────────────────────────────────────────────────────────


def _admin_models():
    return [m for m in admin.site._registry]


@pytest.mark.parametrize("model", _admin_models(), ids=lambda m: m._meta.label)
def test_every_admin_changelist_and_form_renders(admin_client, model):
    opts = model._meta
    changelist = admin_client.get(reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"), follow=True)
    assert changelist.status_code == 200
    obj = model.objects.first()
    if obj is not None:
        change = admin_client.get(reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk]))
        assert change.status_code == 200


def test_admin_dashboard_renders(admin_client):
    assert admin_client.get(reverse("admin:index")).status_code == 200


def test_users_and_groups_use_the_admin_theme(admin_client, superuser):
    from django.contrib import admin
    from django.contrib.auth.models import Group, User
    from unfold.admin import ModelAdmin

    assert isinstance(admin.site._registry[User], ModelAdmin)
    assert isinstance(admin.site._registry[Group], ModelAdmin)
    for url in (
        reverse("admin:auth_user_change", args=[superuser.pk]),
        reverse("admin:auth_user_add"),
        reverse("admin:auth_user_password_change", args=[superuser.pk]),
        reverse("admin:auth_group_add"),
    ):
        assert admin_client.get(url).status_code == 200, url


def test_singleton_admin_goes_straight_to_the_record(admin_client):
    response = admin_client.get(reverse("admin:site_config_sitesettings_changelist"))
    assert response.status_code == 302
    assert response["Location"].endswith(f"/{SiteSettings.SINGLETON_PK}/change/")


def test_arabic_inputs_are_right_to_left(admin_client):
    page = Page.objects.get(slug="about-company")
    html = admin_client.get(reverse("admin:pages_page_change", args=[page.pk])).content.decode()
    tag = re.search(r'<input[^>]*name="title_ar"[^>]*>', html).group(0)
    assert 'dir="rtl"' in tag and 'lang="ar"' in tag
    english = re.search(r'<input[^>]*name="title_en"[^>]*>', html).group(0)
    assert 'dir="rtl"' not in english


def test_editing_a_page_through_the_admin_updates_the_api(admin_client, api, django_capture_on_commit_callbacks):
    page = Page.objects.get(slug="certificates")
    form_url = reverse("admin:pages_page_change", args=[page.pk])
    data = {
        "slug": page.slug, "template": page.template, "is_published": "on", "order": page.order,
        "title_en": "Accreditations", "title_ar": page.title_ar,
        "eyebrow_en": page.eyebrow_en, "eyebrow_ar": page.eyebrow_ar,
        "lede_en": page.lede_en, "lede_ar": page.lede_ar,
        "meta_title_en": "", "meta_title_ar": "",
        "meta_description_en": page.meta_description_en, "meta_description_ar": page.meta_description_ar,
        "blocks-TOTAL_FORMS": page.blocks.count(), "blocks-INITIAL_FORMS": page.blocks.count(),
        "blocks-MIN_NUM_FORMS": 0, "blocks-MAX_NUM_FORMS": 1000,
    }
    for i, block in enumerate(page.blocks.all()):
        data.update({f"blocks-{i}-id": block.pk, f"blocks-{i}-page": page.pk, f"blocks-{i}-order": block.order, f"blocks-{i}-is_visible": "on"})
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(form_url, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    assert api.get("/api/v1/pages/certificates/").json()["data"]["title"] == "Accreditations"


def test_missing_arabic_is_detected():
    item = NavigationItem.objects.get(key="news-events")
    assert missing_arabic(item) == []
    item.label_ar = ""
    assert missing_arabic(item) == ["label"]


def test_seeded_content_is_fully_translated():
    gaps = [(b.page.slug, b.order, missing_arabic(b)) for b in PageBlock.objects.select_related("page") if missing_arabic(b)]
    assert gaps == []


# ── OpenAPI ──────────────────────────────────────────────────────────────────────────


def test_schema_generates_without_warnings(tmp_path):
    out = tmp_path / "schema.yml"
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(out))
    schema = yaml.safe_load(out.read_text(encoding="utf-8"))
    paths = schema["paths"]
    assert {"/api/v1/site/", "/api/v1/home/", "/api/v1/pages/{slug}/", "/api/v1/clients/", "/api/v1/enquiries/"} <= set(paths)
    ok = paths["/api/v1/pages/{slug}/"]["get"]["responses"]
    assert {"200", "404", "429", "500"} <= set(ok)
    params = {p["name"] for p in paths["/api/v1/clients/"]["get"]["parameters"]}
    assert {"lang", "page", "page_size", "region", "search", "ordering"} <= params
    created = paths["/api/v1/enquiries/"]["post"]["responses"]
    assert {"201", "400", "409", "415"} <= set(created)


def test_schema_and_docs_are_served(client):
    assert client.get("/api/v1/schema/").status_code == 200
    assert client.get("/api/v1/docs/").status_code == 200


# ── Seed ─────────────────────────────────────────────────────────────────────────────


def test_seed_is_idempotent():
    before = (Client.objects.count(), PageBlock.objects.count(), NavigationItem.objects.count())
    call_command("seed_content", verbosity=0)
    after = (Client.objects.count(), PageBlock.objects.count(), NavigationItem.objects.count())
    assert before == after == (367, 45, 22)


def test_seed_file_is_valid_json_with_both_languages(settings):
    data = json.loads((settings.BASE_DIR / "seed" / "content.json").read_text(encoding="utf-8"))
    assert all(set(p["title"]) == {"en", "ar"} for p in data["pages"])
