"""How the team hears about a new enquiry.

The service depends on the `EnquiryNotifier` protocol, not on e-mail: the concrete class is
chosen in settings (ENQUIRY_NOTIFIER) and injected, so tests use a recording fake and a
deployment can swap in Slack or a CRM adapter without touching the service.
"""

import logging
from typing import Protocol

from django.conf import settings
from django.core.mail import send_mail
from django.utils.module_loading import import_string

from config.api_exceptions import ExternalServiceException

from .models import Enquiry

logger = logging.getLogger("apps.enquiries")


def team_notification_address() -> str | None:
    """Where the team is told about website submissions: Site settings → "Send enquiries
    to", else ENQUIRY_NOTIFICATION_EMAIL. Shared with client reviews."""
    from apps.site_config.models import SiteSettings

    configured = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_PK).values_list(
        "enquiry_notification_email", flat=True
    ).first()
    return configured or settings.ENQUIRY_NOTIFICATION_EMAIL or None


class EnquiryNotifier(Protocol):
    def notify(self, enquiry: Enquiry) -> None: ...


class NullEnquiryNotifier:
    def notify(self, enquiry: Enquiry) -> None:
        logger.info("Enquiry %s received (notifications disabled)", enquiry.pk)


class EmailEnquiryNotifier:
    """Adapter from the notifier protocol to Django's mail API."""

    def __init__(self, recipient: str | None = None):
        self._recipient = recipient

    def _resolve_recipient(self) -> str | None:
        return self._recipient or team_notification_address()

    def notify(self, enquiry: Enquiry) -> None:
        recipient = self._resolve_recipient()
        if not recipient:
            logger.warning("Enquiry %s received but no notification address is configured", enquiry.pk)
            return
        body = (
            f"Name: {enquiry.full_name}\n"
            f"E-mail: {enquiry.email}\n"
            f"Phone: {enquiry.phone or '—'}\n"
            f"Company: {enquiry.company or '—'}\n"
            f"Language: {enquiry.language}\n"
            f"Page: {enquiry.source_path or '—'}\n\n"
            f"{enquiry.message}\n"
        )
        try:
            send_mail(
                subject=f"Website enquiry from {enquiry.full_name}",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
            )
        except Exception as exc:  # SMTP, DNS, auth — all "the mail service failed"
            raise ExternalServiceException() from exc


def get_enquiry_notifier() -> EnquiryNotifier:
    return import_string(settings.ENQUIRY_NOTIFIER)()
