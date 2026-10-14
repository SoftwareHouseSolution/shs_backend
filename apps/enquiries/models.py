from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Enquiry(TimeStampedModel):
    """A message sent from the website's contact form."""

    class Status(models.TextChoices):
        NEW = "new", _("New")
        IN_PROGRESS = "in_progress", _("In progress")
        CLOSED = "closed", _("Closed")

    full_name = models.CharField(_("name"), max_length=120)
    email = models.EmailField(_("e-mail"), db_index=True)
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    company = models.CharField(_("company"), max_length=160, blank=True)
    message = models.TextField(_("message"))
    language = models.CharField(_("language"), max_length=5, choices=settings.LANGUAGES, default="en")
    source_path = models.CharField(_("sent from page"), max_length=255, blank=True)
    status = models.CharField(_("status"), max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    internal_notes = models.TextField(_("internal notes"), blank=True)

    class Meta:
        verbose_name = _("enquiry")
        verbose_name_plural = _("enquiries")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email", "created_at"], name="enquiry_email_created")]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"
