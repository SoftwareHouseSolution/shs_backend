"""Business rules for client reviews: storing a submission and publishing it as a
testimonial. Testable without HTTP."""

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.content.models import Testimonial
from apps.core.codes import ResponseCode
from config.api_exceptions import ResourceConflictException

from .models import Review
from .notifiers import ReviewNotifier, get_review_notifier

logger = logging.getLogger("apps.reviews")


class PublishRefused(Exception):
    """The review cannot become a testimonial (the client did not consent)."""


@dataclass(frozen=True)
class ReviewInput:
    author_name: str
    shop_name: str
    governorate: str
    area: str
    duration: str
    support: str
    updates: str
    text: str
    benefits: list[str] = field(default_factory=list)
    comment: str = ""
    consent: bool = False
    source: str = ""


class ReviewService:
    def __init__(self, notifier: ReviewNotifier, duplicate_window: timedelta):
        self._notifier = notifier
        self._duplicate_window = duplicate_window

    @classmethod
    def from_settings(cls) -> "ReviewService":
        return cls(
            notifier=get_review_notifier(),
            duplicate_window=timedelta(minutes=settings.ENQUIRY_DUPLICATE_WINDOW_MINUTES),
        )

    def submit(self, data: ReviewInput, *, photo=None, language: str) -> Review:
        """Store the review and tell the team once it is committed. Raises
        ResourceConflictException(DUPLICATE_REVIEW) when the same shop sent the same text
        within the duplicate window (a double tap on "Send")."""
        with transaction.atomic():
            since = timezone.now() - self._duplicate_window
            if Review.objects.filter(shop_name__iexact=data.shop_name, text=data.text, created_at__gte=since).exists():
                raise ResourceConflictException(code=ResponseCode.DUPLICATE_REVIEW)
            review = Review(**data.__dict__, language=language)
            if photo:
                review.photo = photo
            review.save()
            transaction.on_commit(lambda: self._notify(review))
        logger.info("Review %s stored", review.pk)
        return review

    def _notify(self, review: Review) -> None:
        # The review is stored; a failed e-mail must not turn the client's submission into
        # an error. It is logged (and shows on Admin → System status).
        try:
            self._notifier.notify(review)
        except Exception:
            logger.exception("Notification for review %s failed", review.pk)


def publish(review: Review) -> Testimonial:
    """Turn a review into a published testimonial on the website. Idempotent: a review that
    already has its testimonial returns it. Refused when the client did not consent."""
    if review.testimonial_id:
        return review.testimonial
    if not review.consent:
        raise PublishRefused(review)
    lang = review.language if review.language in ("en", "ar") else "ar"
    with transaction.atomic():
        # Newest first: the new testimonial takes the top slot and the rest move down one,
        # so it shows first on the site; editors can still drag it elsewhere.
        Testimonial.objects.update(order=F("order") + 1)
        testimonial = Testimonial(order=0, is_published=True)
        setattr(testimonial, f"quote_{lang}", review.text)
        setattr(testimonial, f"author_name_{lang}", review.author_name)
        setattr(testimonial, f"author_company_{lang}", f"{review.shop_name} — {review.place}")
        if review.photo:
            testimonial.avatar = review.photo.name  # the same stored file, not a copy
        testimonial.save()
        review.testimonial = testimonial
        review.status = Review.Status.PUBLISHED
        review.save(update_fields=["testimonial", "status", "updated_at"])
    return testimonial
