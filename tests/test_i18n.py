import pytest
from django.test import RequestFactory

from apps.core.i18n import UnsupportedLanguage, resolve_language
from apps.site_config.models import NavigationItem

rf = RequestFactory()


@pytest.mark.parametrize(
    ("query", "header", "expected", "source"),
    [
        ("ar", "", "ar", "query"),
        ("EN", "ar", "en", "query"),  # explicit param beats the header, case-insensitive
        ("", "ar-EG,ar;q=0.9,en;q=0.5", "ar", "header"),
        ("", "fr-FR,de;q=0.8", "en", "default"),  # nothing supported → default
        ("", "fr,en-GB;q=0.7", "en", "header"),  # first SUPPORTED entry wins
        ("", "", "en", "default"),
    ],
)
def test_resolution_chain(query, header, expected, source):
    request = rf.get("/api/v1/site/", {"lang": query} if query else {}, HTTP_ACCEPT_LANGUAGE=header)
    resolution = resolve_language(request)
    assert (resolution.language, resolution.source) == (expected, source)


def test_explicit_unsupported_language_is_an_error():
    with pytest.raises(UnsupportedLanguage):
        resolve_language(rf.get("/api/v1/site/", {"lang": "fr"}))


@pytest.mark.django_db
def test_accept_language_header_selects_arabic(api):
    response = api.get("/api/v1/pages/about-company/", HTTP_ACCEPT_LANGUAGE="ar")
    assert response["Content-Language"] == "ar"
    assert response.json()["data"]["title"] == "عن الشركة"
    assert "Accept-Language" in response["Vary"]


@pytest.mark.django_db
def test_missing_arabic_falls_back_to_english(api):
    item = NavigationItem.objects.get(key="news-events")
    item.label_ar = ""
    item.save()
    nav = api.get("/api/v1/site/", {"lang": "ar"}).json()["data"]["navigation"]
    entry = next(e for e in nav if e["key"] == "news-events")
    assert entry["label"] == "News & Events"


@pytest.mark.django_db
def test_missing_english_falls_back_to_arabic(api):
    item = NavigationItem.objects.get(key="news-events")
    item.label_en = ""
    item.save()
    nav = api.get("/api/v1/site/", {"lang": "en"}).json()["data"]["navigation"]
    entry = next(e for e in nav if e["key"] == "news-events")
    assert entry["label"] == "الأخبار والفعاليات"


@pytest.mark.django_db
def test_languages_do_not_mix_in_one_response(api):
    en = api.get("/api/v1/home/", {"lang": "en"}).json()["data"]
    ar = api.get("/api/v1/home/", {"lang": "ar"}).json()["data"]
    assert en["services"]["heading"] != ar["services"]["heading"]
    assert all(not any("؀" <= ch <= "ۿ" for ch in s["title"]) for s in en["hero"])
    assert all(any("؀" <= ch <= "ۿ" for ch in s["title"]) for s in ar["hero"])
