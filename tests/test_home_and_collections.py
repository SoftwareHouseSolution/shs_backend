from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.clients.models import Client, Region
from apps.content import models as content_models
from apps.core.cache import bump_content_version
from apps.events.models import Event
from apps.home.models import HeroSlide, HomePage, HomeStat
from tests.contract import assert_envelope

pytestmark = pytest.mark.django_db


# ── Home ─────────────────────────────────────────────────────────────────────────────


def test_home_payload_sections(api):
    data = api.get("/api/v1/home/").json()["data"]
    assert len(data["hero"]) == 4
    assert data["hero"][0]["video"]["mp4"].endswith(".mp4")
    assert data["hero"][1]["video"] is None
    assert [s.get("text") or s["value"] for s in data["figures"]["stats"]] == ["1988", 1750, 96, 35, "24/7"]
    assert [c["slug"] for c in data["proof"]["highlighted"]] == ["kirmena-jewellery", "gold-era-jewelry", "king-gold-jewellery"]
    assert len(data["proof"]["strip"]) == 48
    assert len(data["services"]["items"]) == 4 and len(data["big_picture"]["items"]) == 4
    assert [s["n"] for s in data["how_to"]["items"]] == ["01", "02", "03"]
    assert data["specs"]["columns"][0] == {"label": "SWH", "highlight": True}
    assert data["testimonial"]["attribution"] == "Mr. Mohammed Wassem — Wassem Jewellery"
    assert len(data["events"]["items"]) == 4 and data["events"]["items"][0]["photo"]["src"]


def test_unpublished_hero_slides_are_hidden(api):
    HeroSlide.objects.filter(order=3).update(is_published=False)
    assert len(api.get("/api/v1/home/").json()["data"]["hero"]) == 3


def test_arabic_hero_artwork_is_used_when_supplied(api):
    slide = HeroSlide.objects.get(order=1)
    slide.image_ar.name = "hero/arabic-artwork.jpg"
    slide.save()
    en = api.get("/api/v1/home/", {"lang": "en"}).json()["data"]["hero"][1]["image"]
    ar = api.get("/api/v1/home/", {"lang": "ar"}).json()["data"]["hero"][1]["image"]
    assert ar.endswith("arabic-artwork.jpg") and not en.endswith("arabic-artwork.jpg")


def test_removing_the_comparison_table_hides_the_section(api):
    HomePage.objects.update(specs_table=None)
    assert api.get("/api/v1/home/").json()["data"]["specs"] is None


def test_stat_is_a_number_or_a_text_never_both():
    home = HomePage.load()
    with pytest.raises(IntegrityError), transaction.atomic():
        HomeStat.objects.create(home=home, label_en="Both", value=5, text="five")
    with pytest.raises(IntegrityError), transaction.atomic():
        HomeStat.objects.create(home=home, label_en="Neither")


def test_video_slide_needs_an_mp4_fallback():
    slide = HeroSlide.objects.get(order=0)
    slide.video_mp4 = ""
    with pytest.raises(ValidationError) as exc:
        slide.full_clean()
    assert "video_mp4" in exc.value.message_dict


def test_featuring_a_testimonial_unfeatures_the_previous_one():
    first = content_models.Testimonial.objects.get(is_featured=True)
    second = content_models.Testimonial.objects.create(quote_en="Great.", author_name_en="A. Client", is_featured=True)
    first.refresh_from_db()
    assert second.is_featured and not first.is_featured
    assert content_models.Testimonial.objects.filter(is_featured=True).count() == 1


# ── Clients ──────────────────────────────────────────────────────────────────────────


def test_client_list_is_paginated_and_can_be_loaded_whole(api):
    body = api.get("/api/v1/clients/").json()
    assert body["meta"]["pagination"]["count"] == 367
    assert body["meta"]["pagination"]["page_size"] == 100
    whole = api.get("/api/v1/clients/", {"page_size": 500}).json()
    assert len(whole["data"]) == 367 and whole["meta"]["pagination"]["next"] is None
    capped = api.get("/api/v1/clients/", {"page_size": 10_000}).json()
    assert capped["meta"]["pagination"]["page_size"] == 500


def test_out_of_range_page_is_a_404(api):
    from apps.core.codes import ResponseCode

    assert_envelope(api.get("/api/v1/clients/", {"page": 999}), status=404, code=ResponseCode.RESOURCE_NOT_FOUND)


@pytest.mark.parametrize(
    ("params", "check"),
    [
        ({"region": "giza"}, lambda c: c["region"] == "giza"),
        ({"sector": "enterprise"}, lambda c: c["sector"] == "enterprise"),
        ({"business_type": "manufacturing"}, lambda c: "manufacturing" in c["business_types"]),
        ({"featured": "true"}, lambda c: c["featured_order"] is not None),
        ({"search": "gold"}, lambda c: "gold" in (c["name"] + c["location"]).lower()),
    ],
)
def test_client_filters(api, params, check):
    data = api.get("/api/v1/clients/", {**params, "page_size": 500}).json()["data"]
    assert data and all(check(c) for c in data)


def test_client_ordering(api):
    data = api.get("/api/v1/clients/", {"featured": "true", "ordering": "featured_order"}).json()["data"]
    assert [c["featured_order"] for c in data] == list(range(16))
    names = [c["name"] for c in api.get("/api/v1/clients/", {"ordering": "-name", "page_size": 5}).json()["data"]]
    assert names == sorted(names, reverse=True)


def test_taxonomy_counts_only_published_clients(api):
    before = {r["key"]: r["client_count"] for r in api.get("/api/v1/clients/taxonomy/").json()["data"]["regions"]}
    Client.objects.filter(region__key="giza").update(is_published=False)
    bump_content_version()  # what the admin's bulk publish actions do after .update()
    after = api.get("/api/v1/clients/taxonomy/").json()["data"]
    assert {r["key"]: r["client_count"] for r in after["regions"]}["giza"] == 0
    assert after["total_clients"] == sum(before.values()) - before["giza"]
    pins = {r["key"]: r["map_pin"] for r in after["regions"]}
    assert pins["greater-cairo"] == {"lat": 30.05, "lng": 31.25}
    assert pins["international"] is None


def test_region_pin_needs_both_coordinates():
    with pytest.raises(IntegrityError), transaction.atomic():
        Region.objects.create(key="half", name_en="Half", map_latitude=Decimal("30.0"))


# ── Events, testimonials, partners ───────────────────────────────────────────────────


def test_event_paragraphs_and_photos(api):
    data = api.get("/api/v1/events/nebu-expo-2023/", {"lang": "ar"}).json()["data"]
    assert data["year"] == "2023" and len(data["paras"]) == 3 and len(data["photos"]) == 4
    assert data["title"] == "معرض NEBU 2023"


def test_unpublished_event_leaves_timeline_and_detail(api):
    Event.objects.filter(slug="nebu-expo-2023").update(is_published=False)
    assert api.get("/api/v1/events/nebu-expo-2023/").status_code == 404
    assert len(api.get("/api/v1/events/").json()["data"]) == 3


def test_partner_category_filter(api):
    assert len(api.get("/api/v1/partners/", {"category": "technology"}).json()["data"]) == 5
    assert api.get("/api/v1/partners/", {"category": "business"}).json()["data"] == []
    from apps.core.codes import ResponseCode

    body = assert_envelope(api.get("/api/v1/partners/", {"category": "nope"}), status=400, code=ResponseCode.VALIDATION_ERROR)
    assert "category" in body["errors"]


def test_testimonials_list(api):
    data = api.get("/api/v1/testimonials/").json()["data"]
    assert data[0]["author_name"] == "Mr. Mohammed Wassem"
