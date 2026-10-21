"""Client reviews: the website's review page posts here; editors publish from the admin."""

import io
from datetime import timedelta

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.throttling import SimpleRateThrottle

from apps.content import models as content
from apps.core.codes import ResponseCode
from apps.reviews.models import Review
from apps.reviews.notifiers import EmailReviewNotifier
from apps.reviews.services import ReviewInput, ReviewService, publish, withdraw
from config.api_exceptions import ResourceConflictException
from tests.contract import assert_envelope

pytestmark = pytest.mark.django_db

URL = "/api/v1/reviews/"
TEXT = "بقالي أكتر من ٥ سنين شغال على برنامج سوفت وير هاوس، والدعم الفني ممتاز."
VALID = {
    "author_name": "الحاج طارق",
    "shop_name": "مجوهرات النور",
    "governorate": "القاهرة",
    "area": "الصاغة – الموسكي",
    "duration": "5-10",
    "support": "good",
    "updates": "ok",
    "benefits": ["inventory", "invoices"],
    "text": TEXT,
}


def _jpeg() -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "gold").save(buf, "JPEG")
    return SimpleUploadedFile("shop.jpg", buf.getvalue(), content_type="image/jpeg")


def _review(**overrides) -> Review:
    return Review.objects.create(**{**VALID, "language": "ar", **overrides})


# ── API ──────────────────────────────────────────────────────────────────────────────


def test_a_review_with_a_photo_is_stored(api, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    body = assert_envelope(
        api.post(f"{URL}?lang=ar", {**VALID, "photo": _jpeg(), "source": "Facebook!"}, format="multipart"),
        status=201,
        code=ResponseCode.REVIEW_CREATED,
    )
    review = Review.objects.get()
    assert body["data"]["reference"] == review.reference
    assert review.benefits == ["inventory", "invoices"]
    assert review.language == "ar" and review.source == "facebook"
    assert review.photo.name.startswith("reviews/") and (tmp_path / review.photo.name).exists()
    assert review.status == Review.Status.NEW


def test_the_success_message_is_in_the_requested_language(api):
    body = api.post(f"{URL}?lang=ar", VALID, format="multipart").json()
    assert body["message"] != "Thank you! Your review has reached us. It means a lot to us."


def test_json_without_a_photo_is_accepted(api):
    assert_envelope(api.post(URL, VALID, format="json"), status=201, code=ResponseCode.REVIEW_CREATED)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("support", "amazing"),
        ("duration", "forever"),
        ("benefits", ["inventory", "teleportation"]),
        ("benefits", []),
        ("text", "short"),
        ("author_name", ""),
    ],
)
def test_invalid_answers_are_rejected_per_field(api, field, value):
    body = assert_envelope(api.post(URL, {**VALID, field: value}, format="json"), status=400, code=ResponseCode.VALIDATION_ERROR)
    assert field in body["errors"]
    assert not Review.objects.exists()


def test_a_non_image_photo_is_rejected(api):
    fake = SimpleUploadedFile("shop.jpg", b"MZ not an image", content_type="image/jpeg")
    body = assert_envelope(api.post(URL, {**VALID, "photo": fake}, format="multipart"), status=400, code=ResponseCode.VALIDATION_ERROR)
    assert "photo" in body["errors"]


def test_a_double_tap_is_a_duplicate(api):
    assert_envelope(api.post(URL, VALID, format="multipart"), status=201, code=ResponseCode.REVIEW_CREATED)
    assert_envelope(api.post(URL, VALID, format="multipart"), status=409, code=ResponseCode.DUPLICATE_REVIEW)
    assert Review.objects.count() == 1


def test_bots_filling_the_honeypot_are_silently_dropped(api):
    assert_envelope(api.post(URL, {**VALID, "website": "http://spam"}, format="multipart"), status=201, code=ResponseCode.REVIEW_CREATED)
    assert not Review.objects.exists()


def test_submissions_are_rate_limited(api, monkeypatch):
    rates = {**SimpleRateThrottle.THROTTLE_RATES, "reviews": "1/hour"}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)
    assert api.post(URL, VALID, format="multipart").status_code == 201
    other = {**VALID, "shop_name": "Other shop"}
    assert_envelope(api.post(URL, other, format="multipart"), status=429, code=ResponseCode.RATE_LIMIT_EXCEEDED)


def test_the_share_link_is_part_of_the_site_settings(api):
    from apps.site_config.models import SiteSettings

    SiteSettings.objects.update(review_share_url="https://www.facebook.com/share/p/abc/")
    data = api.get("/api/v1/site/").json()["data"]
    assert data["settings"]["review_share_url"] == "https://www.facebook.com/share/p/abc/"


# ── Service ──────────────────────────────────────────────────────────────────────────


class RecordingNotifier:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def notify(self, review):
        if self.fail:
            raise RuntimeError("smtp down")
        self.sent.append(review.pk)


def _input(**overrides) -> ReviewInput:
    return ReviewInput(**{**VALID, **overrides})


def test_the_team_is_told_after_commit(django_capture_on_commit_callbacks):
    notifier = RecordingNotifier()
    with django_capture_on_commit_callbacks(execute=True):
        review = ReviewService(notifier, timedelta(minutes=10)).submit(_input(), language="ar")
    assert notifier.sent == [review.pk]


def test_a_failed_notification_keeps_the_review(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        ReviewService(RecordingNotifier(fail=True), timedelta(minutes=10)).submit(_input(), language="ar")
    assert Review.objects.count() == 1


def test_the_same_text_from_another_shop_is_not_a_duplicate():
    service = ReviewService(RecordingNotifier(), timedelta(minutes=10))
    service.submit(_input(), language="ar")
    service.submit(_input(shop_name="Another shop"), language="ar")
    with pytest.raises(ResourceConflictException):
        service.submit(_input(), language="ar")


def test_the_e_mail_flags_low_ratings(settings):
    settings.ENQUIRY_NOTIFICATION_EMAIL = "team@example.com"
    from apps.site_config.models import SiteSettings

    SiteSettings.objects.update(enquiry_notification_email="")
    EmailReviewNotifier().notify(_review(support="low"))
    assert mail.outbox[0].subject.startswith("FOLLOW UP:")
    assert "مجوهرات النور" in mail.outbox[0].body


# ── Publishing ───────────────────────────────────────────────────────────────────────


def test_publishing_creates_a_live_testimonial_once():
    review = _review(photo="reviews/shop.jpg")
    testimonial = publish(review)
    assert testimonial.is_published and testimonial.quote_ar == review.text
    assert testimonial.author_name_ar == "الحاج طارق"
    assert testimonial.author_company_ar == "مجوهرات النور — الصاغة – الموسكي، القاهرة"
    assert testimonial.avatar.name == "reviews/shop.jpg"
    review.refresh_from_db()
    assert review.status == Review.Status.PUBLISHED and review.testimonial == testimonial
    assert publish(review) == testimonial and content.Testimonial.objects.filter(review=review).count() == 1


def test_removing_from_the_website_hides_and_archives_and_publishing_restores():
    review = _review()
    testimonial = publish(review)
    assert withdraw(review) is True
    testimonial.refresh_from_db()
    review.refresh_from_db()
    assert not testimonial.is_published and review.status == Review.Status.ARCHIVED
    assert withdraw(review) is False  # already off the website
    assert publish(review) == testimonial
    testimonial.refresh_from_db()
    assert testimonial.is_published and review.status == Review.Status.PUBLISHED


def test_a_published_review_appears_in_the_testimonials_api(api):
    publish(_review())
    quotes = [t["quote"] for t in api.get("/api/v1/testimonials/?lang=ar").json()["data"]]
    assert TEXT in quotes


# ── Admin ────────────────────────────────────────────────────────────────────────────


def test_the_inbox_lists_and_opens_reviews(admin_client):
    review = _review(support="low")
    assert admin_client.get(reverse("admin:reviews_review_changelist")).status_code == 200
    page = admin_client.get(reverse("admin:reviews_review_change", args=[review.pk]))
    assert page.status_code == 200 and review.reference.encode() in page.content


def test_the_top_button_publishes_and_then_removes(admin_client):
    review = _review()
    change = reverse("admin:reviews_review_change", args=[review.pk])
    publish_url = reverse("admin:reviews_review_publish_this", args=[review.pk])
    withdraw_url = reverse("admin:reviews_review_withdraw_this", args=[review.pk])

    page = admin_client.get(change).content.decode()
    assert publish_url in page and withdraw_url not in page

    response = admin_client.get(publish_url)
    assert response.status_code == 302 and response["Location"] == change
    review.refresh_from_db()
    assert review.status == Review.Status.PUBLISHED and review.testimonial.is_published

    page = admin_client.get(change).content.decode()
    assert withdraw_url in page and publish_url not in page

    admin_client.get(withdraw_url)
    review.refresh_from_db()
    assert review.status == Review.Status.ARCHIVED and not review.testimonial.is_published


def test_bulk_actions_publish_and_remove(admin_client):
    a, b = _review(), _review(shop_name="Second shop")
    changelist = reverse("admin:reviews_review_changelist")
    admin_client.post(changelist, {"action": "publish_selected", "_selected_action": [a.pk, b.pk]})
    assert Review.objects.filter(status=Review.Status.PUBLISHED).count() == 2
    admin_client.post(changelist, {"action": "withdraw_selected", "_selected_action": [a.pk]})
    a.refresh_from_db()
    assert a.status == Review.Status.ARCHIVED and not a.testimonial.is_published


def test_the_dashboard_shows_the_review_breakdown(admin_client):
    _review(support="good", benefits=["inventory"])
    _review(support="low", shop_name="Second shop", benefits=["inventory", "invoices"])
    context = admin_client.get(reverse("admin:index")).context
    assert context["review_total"] == 2
    support = {row["label"]: row["count"] for row in context["review_support"]}
    assert support == {"Excellent": 1, "Good": 0, "Needs improvement": 1}
    assert context["review_benefits"][0]["count"] == 2
    assert context["review_kpis"][4]["value"] == 1  # need follow-up


def test_a_newly_published_review_is_listed_first(api):
    publish(_review())
    publish(_review(shop_name="Newest shop", text=TEXT + " جديد"))
    data = api.get("/api/v1/testimonials/?lang=ar").json()["data"]
    assert data[0]["quote"] == TEXT + " جديد" and data[1]["quote"] == TEXT


# ── The status is not edited by hand ─────────────────────────────────────────────────


def test_the_status_cannot_be_changed_from_the_form(admin_client):
    review = _review()
    admin_client.post(
        reverse("admin:reviews_review_change", args=[review.pk]),
        {"status": "published", "internal_notes": "called him back", "_save": "Save"},
    )
    review.refresh_from_db()
    assert review.status == Review.Status.NEW and review.testimonial_id is None
    assert review.internal_notes == "called him back"


def test_the_repair_migration_publishes_reviews_marked_published():
    import importlib

    from django.apps import apps

    repair = importlib.import_module("apps.reviews.migrations.0002_publish_reviews_marked_published")
    marked = _review(status=Review.Status.PUBLISHED, photo="reviews/shop.jpg")

    repair.publish_marked_reviews(apps, None)

    marked.refresh_from_db()
    assert marked.testimonial.is_published and marked.testimonial.quote_ar == TEXT
    assert marked.testimonial.author_company_ar == "مجوهرات النور — الصاغة – الموسكي، القاهرة"
    assert marked.testimonial.order == 0 and marked.testimonial.avatar.name == "reviews/shop.jpg"
