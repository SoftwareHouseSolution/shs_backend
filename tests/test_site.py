import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.codes import ResponseCode
from apps.site_config.models import NavigationItem, SiteSettings, SocialLink
from tests.contract import assert_envelope

pytestmark = pytest.mark.django_db


def test_site_payload_matches_the_frontend_shape(api):
    data = api.get("/api/v1/site/", {"lang": "ar"}).json()["data"]
    assert data["language"] == {"code": "ar", "dir": "rtl"}
    assert data["settings"]["primary_cta"] == {"label": "احجز عرضًا توضيحيًا", "url": "/#contact"}
    assert data["settings"]["contact"] == {
        "heading": "تواصل معنا.",
        "body": "دعنا نطلعك على مزيد من التفاصيل حول حلولنا البرمجية.",
        "cta_label": "راسلنا على واتساب",
    }
    assert [e["key"] for e in data["navigation"]] == [
        "home", "about", "solutions", "partners", "customers", "news-events", "careers",
    ]
    about = next(e for e in data["navigation"] if e["key"] == "about")
    assert [c["url"] for c in about["children"]] == [
        "/about-company", "/background-capabilities", "/our-team", "/certificates",
    ]
    assert [c["key"] for c in data["footer_columns"]] == ["company", "explore", "work"]
    explore = next(c for c in data["footer_columns"] if c["key"] == "explore")
    assert [link["url"] for link in explore["links"]] == ["/solutions", "/services", "/customers", "/testimonials", "/case-studies"]
    assert [s["label"] for s in data["social_links"]] == ["LinkedIn", "Instagram", "Facebook"]
    assert data["badges"] == []


def test_inactive_links_and_emptied_groups_are_dropped(api):
    NavigationItem.objects.filter(parent__key="solutions").update(is_active=False)
    NavigationItem.objects.filter(key="vacancies").update(is_active=False)
    nav = api.get("/api/v1/site/").json()["data"]["navigation"]
    keys = [e["key"] for e in nav]
    assert "solutions" not in keys  # a group with nothing in it is a dead end
    careers = next(e for e in nav if e["key"] == "careers")
    assert "vacancies" not in [c["key"] for c in careers["children"]]


def test_unconfigured_site_is_a_404(api):
    SiteSettings.objects.all()._raw_delete(SiteSettings.objects.db)
    assert_envelope(api.get("/api/v1/site/"), status=404, code=ResponseCode.RESOURCE_NOT_FOUND)


def test_navigation_child_requires_a_link_at_model_and_database_level():
    group = NavigationItem.objects.get(key="about")
    child = NavigationItem(parent=group, key="nolink", label_en="No link", url="")
    with pytest.raises(ValidationError) as exc:
        child.full_clean()
    assert "url" in exc.value.message_dict
    with pytest.raises(IntegrityError), transaction.atomic():
        NavigationItem.objects.create(parent=group, key="nolink2", label_en="x", url="")


def test_navigation_is_two_levels_deep():
    child = NavigationItem.objects.get(key="about-company")
    grandchild = NavigationItem(parent=child, key="deep", label_en="Deep", url="/deep")
    with pytest.raises(ValidationError) as exc:
        grandchild.full_clean()
    assert "parent" in exc.value.message_dict


@pytest.mark.parametrize("bad", ["/en/about-company", "javascript:alert(1)", "about us", "/ar"])
def test_links_reject_locale_prefixes_and_unsafe_schemes(bad):
    item = NavigationItem.objects.get(key="news-events")
    item.url = bad
    with pytest.raises(ValidationError):
        item.full_clean()


@pytest.mark.parametrize("good", ["/", "/customers", "/#contact", "#contact", "https://hardwarehouse-sol.com/", "mailto:a@b.co", "tel:+201558856988"])
def test_links_accept_every_site_link_form(good):
    item = NavigationItem.objects.get(key="news-events")
    item.url = good
    item.full_clean()


def test_site_settings_is_a_singleton():
    settings = SiteSettings.load()
    clone = SiteSettings.objects.get(pk=settings.pk)
    clone.pk = None
    clone.save()  # save() pins the primary key back to 1 — an update, not a second row
    assert SiteSettings.objects.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        SiteSettings.objects.bulk_create([SiteSettings(pk=2, **_required_settings())])


def _required_settings():
    s = SiteSettings.load()
    return {f.name: getattr(s, f.name) for f in SiteSettings._meta.concrete_fields if f.name not in ("id",)}


def test_social_platform_is_unique():
    with pytest.raises(IntegrityError), transaction.atomic():
        SocialLink.objects.create(platform="facebook", url="https://facebook.com/x")
