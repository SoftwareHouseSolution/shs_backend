import pytest
from django.core.exceptions import ValidationError

from apps.core.codes import ResponseCode
from apps.pages.admin import ContainedErrorsForm
from apps.pages.blocks import registered_kinds
from apps.pages.models import Page, PageBlock
from tests.contract import assert_envelope

pytestmark = pytest.mark.django_db


def test_every_block_kind_has_a_strategy():
    assert set(registered_kinds()) == set(PageBlock.Kind.values)


def test_page_list_carries_every_route(api):
    body = api.get("/api/v1/pages/", {"page_size": 100}).json()
    slugs = {p["slug"] for p in body["data"]}
    assert len(slugs) == 16
    assert {"about-company", "services", "customers", "news-events", "life-at-swh"} <= slugs


def test_page_detail_shape_and_breadcrumb(api):
    data = api.get("/api/v1/pages/our-team/", {"lang": "ar"}).json()["data"]
    assert data["title"] == "فريق العمل"
    assert data["breadcrumb_parent"] == "من نحن"
    assert data["header_image"].startswith("http://testserver/media/pages/")
    assert data["video"] is None
    assert [b["kind"] for b in data["blocks"]] == ["intro", "steps", "cta"]


def test_blocks_match_the_frontend_union(api):
    blocks = {b["kind"]: b for b in api.get("/api/v1/pages/services/").json()["data"]["blocks"]}
    assert set(blocks["cards"]["items"][0]) == {"title", "body"}
    assert set(blocks["hardware"]["items"][0]) == {"n", "title", "image"}
    assert blocks["hardware"]["items"][0]["image"].startswith("http://testserver/media/")
    assert set(blocks["steps"]["items"][0]) == {"n", "title", "body"}
    cta = blocks["cta"]
    assert cta["href"] == "https://hardwarehouse-sol.com/"

    spec = next(b for b in api.get("/api/v1/pages/background-capabilities/").json()["data"]["blocks"] if b["kind"] == "spec")
    assert [c["highlight"] for c in spec["columns"]] == [True, False, False]
    assert all(len(r["cells"]) == 3 for r in spec["rows"])

    logos = next(b for b in api.get("/api/v1/pages/technology-partners/").json()["data"]["blocks"] if b["kind"] == "logos")
    assert [l["alt"] for l in logos["logos"]] == ["Microsoft", "HP", "Dell", "Zebra", "Bixolon"]

    news = api.get("/api/v1/pages/news-events/").json()["data"]["blocks"]
    timeline = next(b for b in news if b["kind"] == "timeline")
    assert len(timeline["items"]) == 4 and timeline["items"][0]["year"] is None

    gallery = next(b for b in api.get("/api/v1/pages/life-at-swh/").json()["data"]["blocks"] if b["kind"] == "gallery")
    assert len(gallery["items"]) == 4 and set(gallery["items"][0]) == {"src", "alt"}


def test_customers_page_exposes_its_intro_video(api):
    data = api.get("/api/v1/pages/customers/").json()["data"]
    assert data["template"] == "customers"
    assert data["video"]["desktop"].endswith(".mp4") and data["video"]["poster_mobile"].endswith(".jpg")


def test_unpublished_page_is_hidden(api):
    Page.objects.filter(slug="certificates").update(is_published=False)
    assert_envelope(api.get("/api/v1/pages/certificates/"), status=404, code=ResponseCode.RESOURCE_NOT_FOUND)
    slugs = {p["slug"] for p in api.get("/api/v1/pages/", {"page_size": 100}).json()["data"]}
    assert "certificates" not in slugs


def test_hidden_blocks_are_not_served(api):
    page = Page.objects.get(slug="our-team")
    page.blocks.filter(kind="steps").update(is_visible=False)
    kinds = [b["kind"] for b in api.get("/api/v1/pages/our-team/").json()["data"]["blocks"]]
    assert kinds == ["intro", "cta"]


@pytest.mark.parametrize(
    ("kind", "missing"),
    [("cta", {"url", "label_en"}), ("spec", {"comparison_table"}), ("gallery", {"event"}), ("intro", {"heading_en", "body_en"})],
)
def test_block_strategies_validate_required_fields(kind, missing):
    block = PageBlock(page=Page.objects.first(), kind=kind, heading_en="" if kind == "intro" else "Heading", body_en="" if kind == "intro" else "Body")
    with pytest.raises(ValidationError) as exc:
        block.full_clean()
    assert missing <= set(exc.value.message_dict)


def test_inline_form_reports_errors_for_fields_it_does_not_show():
    class Form(ContainedErrorsForm):
        class Meta:
            model = PageBlock
            fields = ["kind", "order", "is_visible"]

    form = Form(data={"kind": "cta", "order": 0, "is_visible": True}, instance=PageBlock(page=Page.objects.first()))
    assert not form.is_valid()  # no ValueError for "url" not being a form field
    assert any("url" in str(e) for e in form.non_field_errors())


def test_page_search_and_template_filter(api):
    data = api.get("/api/v1/pages/", {"template": "customers"}).json()["data"]
    assert [p["slug"] for p in data] == ["customers"]
    data = api.get("/api/v1/pages/", {"search": "Vacancies"}).json()["data"]
    assert [p["slug"] for p in data] == ["vacancies"]
