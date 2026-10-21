from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.media import UploadTo
from apps.core.models import TimeStampedModel
from apps.core.validators import image_validators


class Review(TimeStampedModel):
    """A client's review, sent from the website's review page (/<lang>/review).

    The answers are stored as codes, not sentences, so the dashboard can count them; the
    review text is what the client approved after editing the generated draft. Nothing
    reaches the public site until an editor publishes it as a Testimonial, and only reviews
    whose author consented can be published.
    """

    class Status(models.TextChoices):
        NEW = "new", _("New")
        PUBLISHED = "published", _("Published")
        ARCHIVED = "archived", _("Archived")

    class Duration(models.TextChoices):
        UNDER_1 = "lt1", _("Less than a year")
        YEARS_1_3 = "1-3", _("1–3 years")
        YEARS_3_5 = "3-5", _("3–5 years")
        YEARS_5_10 = "5-10", _("5–10 years")
        OVER_10 = "10+", _("More than 10 years")

    class Rating(models.TextChoices):
        GOOD = "good", _("Excellent")
        OK = "ok", _("Good")
        LOW = "low", _("Needs improvement")

    class Benefit(models.TextChoices):
        INVENTORY = "inventory", _("Inventory")
        WEIGHTS = "weights", _("Weights and karats")
        ACCOUNTS = "accounts", _("Customer and trader accounts")
        DAILY_REPORTS = "daily_reports", _("Daily reports")
        BRANCHES = "branches", _("Branch monitoring")
        INVOICES = "invoices", _("Invoices")
        WORKMANSHIP = "workmanship", _("Workmanship and hallmarking")

    # The reviewer
    author_name = models.CharField(_("name"), max_length=120)
    shop_name = models.CharField(_("shop"), max_length=160)
    governorate = models.CharField(_("governorate"), max_length=80, db_index=True)
    area = models.CharField(_("area"), max_length=120)
    photo = models.ImageField(_("shop photo"), upload_to=UploadTo("reviews"), validators=image_validators, blank=True)
    # The answers
    duration = models.CharField(_("using the system for"), max_length=8, choices=Duration.choices)
    support = models.CharField(_("technical support"), max_length=8, choices=Rating.choices, db_index=True)
    updates = models.CharField(_("updates"), max_length=8, choices=Rating.choices, db_index=True)
    benefits = models.JSONField(_("helped with"), default=list, help_text=_("Benefit codes."))
    comment = models.TextField(_("in their own words"), blank=True)
    text = models.TextField(_("review"))
    consent = models.BooleanField(_("may be published"), default=False)
    # Context
    language = models.CharField(_("language"), max_length=5, choices=settings.LANGUAGES, default="ar")
    source = models.CharField(
        _("source"), max_length=60, blank=True, help_text=_("The ?src= tag of the link the client opened, e.g. facebook.")
    )
    # Follow-up
    status = models.CharField(_("status"), max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    testimonial = models.OneToOneField(
        "content.Testimonial",
        verbose_name=_("testimonial"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review",
    )
    internal_notes = models.TextField(_("internal notes"), blank=True)

    class Meta:
        verbose_name = _("client review")
        verbose_name_plural = _("client reviews")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["shop_name", "created_at"], name="review_shop_created")]

    def __str__(self):
        return f"{self.author_name} — {self.shop_name}"

    @property
    def reference(self) -> str:
        return f"REV-{self.pk:06d}" if self.pk else "REV-000000"

    @property
    def place(self) -> str:
        if not self.area or self.area == self.governorate:
            return self.governorate
        return f"{self.area}، {self.governorate}" if self.language == "ar" else f"{self.area}, {self.governorate}"

    @property
    def needs_follow_up(self) -> bool:
        """The client rated support or updates as needing improvement."""
        return self.Rating.LOW in (self.support, self.updates)

    def benefit_labels(self) -> list[str]:
        labels = dict(self.Benefit.choices)
        return [str(labels.get(code, code)) for code in self.benefits]


# Module-level name for the schema generator (settings.SPECTACULAR_SETTINGS), which
# imports choice sets by dotted path.
ReviewRating = Review.Rating
