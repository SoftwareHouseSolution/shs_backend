from datetime import timedelta

import pytest
from django.core import mail
from rest_framework.throttling import SimpleRateThrottle

from apps.core.codes import ResponseCode
from apps.enquiries.models import Enquiry
from apps.enquiries.notifiers import EmailEnquiryNotifier
from apps.enquiries.services import EnquiryInput, EnquiryService
from config.api_exceptions import ExternalServiceException, ResourceConflictException
from tests.contract import assert_envelope

pytestmark = pytest.mark.django_db

URL = "/api/v1/enquiries/"
VALID = {"full_name": "Mona Adel", "email": "mona@example.com", "message": "We run four branches and want a demo."}


class RecordingNotifier:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def notify(self, enquiry):
        if self.fail:
            raise ExternalServiceException()
        self.sent.append(enquiry.pk)


# ── Service (no HTTP) ────────────────────────────────────────────────────────────────


def test_service_stores_and_notifies_after_commit(django_capture_on_commit_callbacks):
    notifier = RecordingNotifier()
    service = EnquiryService(notifier, duplicate_window=timedelta(minutes=10))
    with django_capture_on_commit_callbacks(execute=True):
        enquiry = service.submit(EnquiryInput(**VALID), language="ar")
    assert enquiry.language == "ar" and enquiry.status == Enquiry.Status.NEW
    assert notifier.sent == [enquiry.pk]


def test_service_rejects_a_duplicate_within_the_window():
    service = EnquiryService(RecordingNotifier(), duplicate_window=timedelta(minutes=10))
    service.submit(EnquiryInput(**VALID), language="en")
    with pytest.raises(ResourceConflictException) as exc:
        service.submit(EnquiryInput(**{**VALID, "email": "MONA@example.com"}), language="en")
    assert exc.value.code == ResponseCode.DUPLICATE_ENQUIRY
    assert Enquiry.objects.count() == 1


def test_service_accepts_the_same_message_after_the_window():
    service = EnquiryService(RecordingNotifier(), duplicate_window=timedelta(minutes=10))
    first = service.submit(EnquiryInput(**VALID), language="en")
    Enquiry.objects.filter(pk=first.pk).update(created_at=first.created_at - timedelta(minutes=11))
    service.submit(EnquiryInput(**VALID), language="en")
    assert Enquiry.objects.count() == 2


def test_failed_notification_does_not_lose_the_enquiry(django_capture_on_commit_callbacks):
    service = EnquiryService(RecordingNotifier(fail=True), duplicate_window=timedelta(minutes=10))
    with django_capture_on_commit_callbacks(execute=True):
        service.submit(EnquiryInput(**VALID), language="en")
    assert Enquiry.objects.count() == 1


def test_email_notifier_sends_to_the_configured_address():
    enquiry = Enquiry.objects.create(**VALID)
    EmailEnquiryNotifier(recipient="sales@example.com").notify(enquiry)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["sales@example.com"]
    assert "Mona Adel" in mail.outbox[0].subject


def test_email_notifier_without_a_recipient_is_a_no_op(settings):
    settings.ENQUIRY_NOTIFICATION_EMAIL = ""
    EmailEnquiryNotifier().notify(Enquiry.objects.create(**VALID))
    assert mail.outbox == []


# ── API ──────────────────────────────────────────────────────────────────────────────


def test_create_returns_201_with_a_reference(api):
    body = assert_envelope(api.post(URL, VALID, format="json"), status=201, code=ResponseCode.ENQUIRY_CREATED)
    assert body["data"]["reference"].startswith("ENQ-")
    assert Enquiry.objects.get().email == "mona@example.com"


def test_create_records_the_request_language(api):
    api.post(URL + "?lang=ar", VALID, format="json")
    assert Enquiry.objects.get().language == "ar"


def test_validation_errors_are_per_field_and_localised(api):
    body = assert_envelope(
        api.post(URL + "?lang=ar", {"email": "nope", "message": "short", "phone": "call me"}, format="json"),
        status=400,
        code=ResponseCode.VALIDATION_ERROR,
    )
    assert set(body["errors"]) == {"full_name", "email", "message", "phone"}
    assert body["message"] == "البيانات المُرسلة غير صحيحة."
    assert body["errors"]["phone"] == ["أدخل رقم هاتف صحيحًا."]


def test_duplicate_is_409(api):
    api.post(URL, VALID, format="json")
    assert_envelope(api.post(URL, VALID, format="json"), status=409, code=ResponseCode.DUPLICATE_ENQUIRY)


def test_honeypot_is_accepted_but_not_stored(api):
    assert_envelope(api.post(URL, {**VALID, "website": "http://spam"}, format="json"), status=201, code=ResponseCode.ENQUIRY_CREATED)
    assert Enquiry.objects.count() == 0


def test_non_json_body_is_415(api):
    assert_envelope(api.post(URL, VALID), status=415, code=ResponseCode.UNSUPPORTED_MEDIA_TYPE)


def test_malformed_json_is_400(api):
    response = api.post(URL, "{not json", content_type="application/json")
    assert_envelope(response, status=400, code=ResponseCode.MALFORMED_REQUEST)


def test_submissions_are_rate_limited(api, monkeypatch):
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", {"anon": "1000/min", "enquiries": "2/hour"})
    for i in range(2):
        api.post(URL, {**VALID, "message": f"Distinct message number {i}"}, format="json")
    response = api.post(URL, {**VALID, "message": "One too many messages."}, format="json")
    body = assert_envelope(response, status=429, code=ResponseCode.RATE_LIMIT_EXCEEDED)
    assert body["meta"]["retry_after"] > 0 and int(response["Retry-After"]) > 0
    # Other methods are not spent from (or blocked by) the submission budget.
    assert_envelope(api.get(URL), status=405, code=ResponseCode.METHOD_NOT_ALLOWED)
