"""Every public endpoint, in both languages, returns the standard envelope."""

import pytest
from django.urls import get_resolver

from apps.core.codes import ResponseCode
from tests.contract import assert_envelope

pytestmark = pytest.mark.django_db

# (url, success code, paginated?)
READ_ENDPOINTS = [
    ("/api/v1/health/", ResponseCode.HEALTH_OK, False),
    ("/api/v1/site/", ResponseCode.CONTENT_RETRIEVED, False),
    ("/api/v1/home/", ResponseCode.CONTENT_RETRIEVED, False),
    ("/api/v1/pages/", ResponseCode.CONTENT_LIST_RETRIEVED, True),
    ("/api/v1/pages/about-company/", ResponseCode.CONTENT_RETRIEVED, False),
    ("/api/v1/clients/", ResponseCode.CONTENT_LIST_RETRIEVED, True),
    ("/api/v1/clients/taxonomy/", ResponseCode.CONTENT_RETRIEVED, False),
    ("/api/v1/events/", ResponseCode.CONTENT_LIST_RETRIEVED, True),
    ("/api/v1/events/nebu-expo-2024/", ResponseCode.CONTENT_RETRIEVED, False),
    ("/api/v1/testimonials/", ResponseCode.CONTENT_LIST_RETRIEVED, True),
    ("/api/v1/partners/", ResponseCode.CONTENT_LIST_RETRIEVED, True),
]

# Routes that are deliberately not JSON-envelope endpoints, or are covered elsewhere.
NOT_IN_SWEEP = {"schema/", "docs/", "redoc/", "enquiries/", "analytics/collect/"}


@pytest.mark.parametrize("lang", ["en", "ar"])
@pytest.mark.parametrize(("url", "code", "paginated"), READ_ENDPOINTS)
def test_read_endpoints_return_the_envelope(api, url, code, paginated, lang):
    response = api.get(url, {"lang": lang})
    body = assert_envelope(response, status=200, code=code)
    assert response["Content-Language"] == lang
    if paginated:
        pagination = body["meta"]["pagination"]
        assert set(pagination) == {"count", "page", "page_size", "total_pages", "next", "previous"}
        assert isinstance(body["data"], list)
    else:
        assert body["meta"] is None


def test_every_api_route_is_in_the_contract_sweep():
    """A new endpoint must be added to READ_ENDPOINTS (or explicitly excluded)."""
    api_patterns = next(p for p in get_resolver().url_patterns if getattr(p, "namespace", None) == "api-v1")
    declared = {str(p.pattern) for p in api_patterns.url_patterns}
    swept = {u.removeprefix("/api/v1/") for u, _c, _p in READ_ENDPOINTS}
    normalised = {
        r.replace("<slug:slug>", "about-company") if r.startswith("pages") else r.replace("<slug:slug>", "nebu-expo-2024")
        for r in declared
    }
    missing = normalised - swept - NOT_IN_SWEEP
    assert not missing, f"Endpoints missing from the contract sweep: {sorted(missing)}"


@pytest.mark.parametrize(
    "url",
    ["/api/v1/pages/does-not-exist/", "/api/v1/events/does-not-exist/", "/api/v1/no-such-endpoint/", "/api/v2/home/"],
)
def test_unknown_resources_are_enveloped_404s(api, url):
    assert_envelope(api.get(url), status=404, code=ResponseCode.RESOURCE_NOT_FOUND)


def test_method_not_allowed_is_enveloped(api):
    response = api.delete("/api/v1/home/")
    assert_envelope(response, status=405, code=ResponseCode.METHOD_NOT_ALLOWED)


def test_unsupported_language_is_a_400_with_a_field_error(api):
    body = assert_envelope(api.get("/api/v1/site/", {"lang": "fr"}), status=400, code=ResponseCode.UNSUPPORTED_LANGUAGE)
    assert "lang" in body["errors"]


def test_inbound_request_id_is_echoed_when_well_formed(api):
    response = api.get("/api/v1/health/", HTTP_X_REQUEST_ID="trace-abc-12345")
    assert response["X-Request-ID"] == "trace-abc-12345"
    junk = api.get("/api/v1/health/", HTTP_X_REQUEST_ID="<script>")
    assert junk["X-Request-ID"] != "<script>"


def test_admin_pages_are_not_converted_to_json(client):
    response = client.get("/admin/login/")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
