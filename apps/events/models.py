"""News & events: exhibitions, client openings, company occasions — each with photos."""

import re

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.media import UploadTo
from apps.core.models import OrderedModel, PublishableModel, TimeStampedModel
from apps.core.validators import image_validators

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


class Event(OrderedModel, PublishableModel, TimeStampedModel):
    slug = models.SlugField(_("slug"), max_length=80, unique=True)
    year = models.CharField(
        _("year"),
        max_length=4,
        blank=True,
        help_text=_("Leave empty when the date is not established — the site shows “Recent”."),
    )
    title = models.CharField(_("title"), max_length=160)
    body = models.TextField(_("story"), help_text=_("Separate paragraphs with a blank line."))

    class Meta(OrderedModel.Meta):
        verbose_name = _("event")
        verbose_name_plural = _("events")

    def __str__(self):
        return f"{self.title} ({self.year})" if self.year else self.title

    @property
    def paragraphs(self) -> list[str]:
        return [p.strip() for p in _PARAGRAPH_BREAK.split(self.body or "") if p.strip()]


class EventPhoto(OrderedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(_("photo"), upload_to=UploadTo("events"), validators=image_validators)
    alt = models.CharField(
        _("description"), max_length=255, help_text=_("What the photo shows, for screen readers.")
    )

    class Meta(OrderedModel.Meta):
        verbose_name = _("photo")
        verbose_name_plural = _("photos")

    def __str__(self):
        return self.alt
