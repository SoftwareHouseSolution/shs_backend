"""How the team hears about a new client review (same pattern as apps.enquiries.notifiers:
the class is chosen by settings.REVIEW_NOTIFIER, so tests and deployments can swap it)."""

import logging
from typing import Protocol

from django.conf import settings
from django.core.mail import send_mail
from django.utils.module_loading import import_string

from apps.enquiries.notifiers import team_notification_address

from .models import Review

logger = logging.getLogger("apps.reviews")


class ReviewNotifier(Protocol):
    def notify(self, review: Review) -> None: ...


class NullReviewNotifier:
    def notify(self, review: Review) -> None:
        logger.info("Review %s received (notifications disabled)", review.pk)


class EmailReviewNotifier:
    def notify(self, review: Review) -> None:
        recipient = team_notification_address()
        if not recipient:
            logger.warning("Review %s received but no notification address is configured", review.pk)
            return
        flag = "FOLLOW UP: " if review.needs_follow_up else ""
        body = (
            f"{flag}New client review {review.reference}\n\n"
            f"Name: {review.author_name}\n"
            f"Shop: {review.shop_name} ({review.place})\n"
            f"Using the system for: {review.get_duration_display()}\n"
            f"Support: {review.get_support_display()}\n"
            f"Updates: {review.get_updates_display()}\n"
            f"Helped with: {', '.join(review.benefit_labels())}\n"
            f"May be published: {'yes' if review.consent else 'no'}\n\n"
            f"{review.text}\n"
            + (f"\nIn their own words:\n{review.comment}\n" if review.comment else "")
        )
        send_mail(
            subject=f"{flag}Client review from {review.shop_name}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
        )


def get_review_notifier() -> ReviewNotifier:
    return import_string(settings.REVIEW_NOTIFIER)()
