"""Every failure class is normalised into the envelope with the right status and code, and
internal detail never reaches the client."""

import logging

import pytest

from apps.core.codes import ResponseCode
from apps.core.logging import RequestIdFilter
from tests.contract import assert_envelope

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.error_urls")]


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
        self.addFilter(RequestIdFilter())

    def emit(self, record):
        self.records.append(record)


def test_unexpected_exception_is_a_safe_500_correlated_with_the_log(api):
    capture = _Capture()
    logger = logging.getLogger("config.api_exceptions")
    logger.addHandler(capture)
    try:
        response = api.get("/api/test/boom/")
    finally:
        logger.removeHandler(capture)
    body = assert_envelope(response, status=500, code=ResponseCode.INTERNAL_SERVER_ERROR)
    text = response.content.decode()
    assert "hunter2" not in text and "Traceback" not in text
    request_id = body["meta"]["request_id"]
    assert request_id == response["X-Request-ID"]
    # The log line holding the traceback carries the same id the client was given.
    [record] = capture.records
    assert record.exc_info is not None
    assert record.request_id == request_id


def test_integrity_error_becomes_409_without_database_detail(api):
    response = api.get("/api/test/integrity/")
    assert_envelope(response, status=409, code=ResponseCode.RESOURCE_CONFLICT)
    assert "pkey" not in response.content.decode()


def test_database_outage_becomes_503(api):
    body = assert_envelope(api.get("/api/test/db-down/"), status=503, code=ResponseCode.SERVICE_UNAVAILABLE)
    assert body["meta"]["request_id"]


def test_django_http404_becomes_enveloped_404(api):
    assert_envelope(api.get("/api/test/http404/"), status=404, code=ResponseCode.RESOURCE_NOT_FOUND)


def test_permission_denied_is_403(api):
    assert_envelope(api.get("/api/test/forbidden/"), status=403, code=ResponseCode.PERMISSION_DENIED)


def test_unauthenticated_is_401_with_challenge(api):
    response = api.get("/api/test/protected/")
    assert_envelope(response, status=401, code=ResponseCode.AUTHENTICATION_REQUIRED)
    assert "WWW-Authenticate" in response


def test_bad_credentials_are_401_authentication_failed(api):
    response = api.get("/api/test/protected/", HTTP_AUTHORIZATION="Basic Zm9vOmJhcg==")
    assert_envelope(response, status=401, code=ResponseCode.AUTHENTICATION_FAILED)


def test_business_rule_keeps_its_message(api):
    body = assert_envelope(api.get("/api/test/business/"), status=422, code=ResponseCode.BUSINESS_RULE_VIOLATION)
    assert body["message"] == "Slot already taken."


def test_upstream_failure_is_502_with_request_id(api):
    body = assert_envelope(api.get("/api/test/upstream/"), status=502, code=ResponseCode.EXTERNAL_SERVICE_ERROR)
    assert body["meta"]["request_id"]


def test_non_field_validation_errors_get_a_stable_key(api):
    body = assert_envelope(api.get("/api/test/non-field/"), status=400, code=ResponseCode.VALIDATION_ERROR)
    assert body["errors"] == {"non_field_errors": ["Dates overlap."]}


def test_throttle_reports_retry_after_in_meta_and_header(api):
    response = api.get("/api/test/throttled/")
    body = assert_envelope(response, status=429, code=ResponseCode.RATE_LIMIT_EXCEEDED)
    assert body["meta"] == {"retry_after": 17}
    assert response["Retry-After"] == "17"


def test_exception_in_a_plain_django_view_under_api_is_still_json(api):
    response = api.get("/api/test/plain/")
    body = assert_envelope(response, status=500, code=ResponseCode.INTERNAL_SERVER_ERROR)
    assert "hunter2" not in response.content.decode()
    assert body["meta"]["request_id"] == response["X-Request-ID"]


def test_error_messages_follow_the_requested_language(api):
    body = assert_envelope(api.get("/api/test/http404/", {"lang": "ar"}), status=404, code=ResponseCode.RESOURCE_NOT_FOUND)
    assert body["message"] == "المورد المطلوب غير موجود."
