from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

MARKDOWN_HELP = _(
    "Simple formatting: a line starting with ## is a heading, - starts a list item, "
    "**text** is bold, [text](/en#contact) is a link. Leave an empty line between paragraphs."
)


class LegalDocument(TimeStampedModel):
    """A legal page of the website — the privacy policy — kept apart from the CMS pages.

    It has its own on/off switch: unpublished, its page and its API answer 404 and its footer
    link disappears. App-store listings point at the privacy policy's URL, so switching it
    off takes that link down too.
    """

    class Kind(models.TextChoices):
        PRIVACY = "privacy", _("Privacy policy")

    slug = models.SlugField(
        _("page"), max_length=40, choices=Kind.choices, unique=True,
        help_text=_("Which legal page this is; it decides the address, e.g. /ar/privacy."),
    )
    title = models.CharField(_("title"), max_length=160)
    body = models.TextField(_("text"), help_text=MARKDOWN_HELP)
    last_updated = models.DateField(_("last updated"), help_text=_("Shown under the title. Change it when the policy changes."))
    is_published = models.BooleanField(
        _("published"), default=True, db_index=True,
        help_text=_("Off: the page and its footer link disappear from the website."),
    )
    show_in_footer = models.BooleanField(_("link in the footer"), default=True)

    class Meta:
        verbose_name = _("legal page")
        verbose_name_plural = _("legal pages")
        ordering = ["slug"]

    def __str__(self):
        return self.title or self.get_slug_display()

    def get_absolute_url(self) -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/ar/{self.slug}"
