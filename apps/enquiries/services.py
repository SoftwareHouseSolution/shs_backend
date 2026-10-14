"""Business rules for enquiries. Testable without HTTP: construct the service with any
notifier and call `submit()`."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.codes import ResponseCode
from config.api_exceptions import ApplicationException, ResourceConflictException

from .models import Enquiry
from .notifiers import EnquiryNotifier, get_enquiry_notifier

logger = logging.getLogger("apps.enquiries")


@dataclass(frozen=True)
class EnquiryInput:
    full_name: str
    email: str
    message: str
    phone: str = ""
    company: str = ""
    source_path: str = ""


class EnquiryService:
    def __init__(self, notifier: EnquiryNotifier, duplicate_window: timedelta):
        self._notifier = notifier
        self._duplicate_window = duplicate_window

    @classmethod
    def from_settings(cls) -> "EnquiryService":
        return cls(
            notifier=get_enquiry_notifier(),
            duplicate_window=timedelta(minutes=settings.ENQUIRY_DUPLICATE_WINDOW_MINUTES),
        )

    def submit(self, data: EnquiryInput, *, language: str) -> Enquiry:
        """Store the enquiry and notify the team once the row is committed.

        Raises ResourceConflictException(DUPLICATE_ENQUIRY) when the same address sent the
        same message within the duplicate window — a double-click or a resubmitted form.
        """
        with transaction.atomic():
            if self._is_duplicate(data):
                raise ResourceConflictException(code=ResponseCode.DUPLICATE_ENQUIRY)
            enquiry = Enquiry.objects.create(
                full_name=data.full_name,
                email=data.email,
                phone=data.phone,
                company=data.company,
                message=data.message,
                source_path=data.source_path,
                language=language,
            )
            transaction.on_commit(lambda: self._notify(enquiry))
        logger.info("Enquiry %s stored", enquiry.pk)
        return enquiry

    def _is_duplicate(self, data: EnquiryInput) -> bool:
        since = timezone.now() - self._duplicate_window
        return Enquiry.objects.filter(
            email__iexact=data.email, message=data.message, created_at__gte=since
        ).exists()

    def _notify(self, enquiry: Enquiry) -> None:
        # The enquiry is already safely stored; a failed notification must not turn the
        # visitor's successful submission into an error. It is logged for follow-up.
        try:
            self._notifier.notify(enquiry)
        except ApplicationException:
            logger.exception("Notification for enquiry %s failed", enquiry.pk)
        except Exception:
            logger.exception("Unexpected notifier failure for enquiry %s", enquiry.pk)
