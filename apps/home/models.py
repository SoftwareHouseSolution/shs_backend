"""The home page: one record of section copy, plus its ordered collections (hero slides,
figures, and the cards of the Services / Big picture / How-to sections)."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.media import LinkField, UploadTo
from apps.core.models import OrderedModel, PublishableModel, SingletonModel, TimeStampedModel
from apps.core.validators import image_validators, video_validators


class HomePage(SingletonModel, TimeStampedModel):
    # SEO
    meta_title = models.CharField(_("page title"), max_length=70, blank=True, help_text=_("Defaults to the site's title."))
    meta_description = models.CharField(_("meta description"), max_length=300, blank=True)

    # Figures band (under the hero)
    figures_eyebrow = models.CharField(_("figures: label"), max_length=120)
    figures_aria_label = models.CharField(_("figures: accessible name"), max_length=120)

    # Client proof band
    proof_lede = models.CharField(_("client band: sentence"), max_length=255)
    proof_strip_aria_label = models.CharField(_("client band: strip accessible name"), max_length=160)
    proof_cta_label = models.CharField(_("client band: button"), max_length=80)
    proof_cta_url = LinkField(_("client band: button link"), default="/customers")

    # Services
    services_eyebrow = models.CharField(_("services: label"), max_length=60)
    services_heading = models.CharField(_("services: heading"), max_length=160)
    services_body = models.TextField(_("services: text"))
    services_image = models.ImageField(_("services: image"), upload_to=UploadTo("home"), validators=image_validators)
    services_image_alt = models.CharField(_("services: image description"), max_length=160)

    # Big picture
    big_picture_heading = models.CharField(_("big picture: heading"), max_length=160)
    big_picture_body = models.TextField(_("big picture: text"))
    big_picture_image = models.ImageField(_("big picture: image"), upload_to=UploadTo("home"), validators=image_validators)
    big_picture_image_alt = models.CharField(_("big picture: image description"), max_length=160)
    discover_more_label = models.CharField(_("“discover more” button"), max_length=60)

    # Comparison
    specs_eyebrow = models.CharField(_("comparison: label"), max_length=60)
    specs_heading = models.CharField(_("comparison: heading"), max_length=160)
    specs_table = models.ForeignKey(
        "content.ComparisonTable",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("comparison table"),
        help_text=_("Leave empty to hide the section."),
    )

    # How-to
    how_to_heading = models.CharField(_("how-to: heading"), max_length=160)

    # Events
    events_eyebrow = models.CharField(_("events: label"), max_length=60)
    events_heading = models.CharField(_("events: heading"), max_length=160)
    events_body = models.TextField(_("events: text"))
    events_cta_label = models.CharField(_("events: button"), max_length=80)
    events_cta_url = LinkField(_("events: button link"), default="/news-events")

    # Closing band
    band_heading = models.CharField(_("closing band: heading"), max_length=160)
    band_body = models.TextField(_("closing band: text"))
    band_cta_label = models.CharField(_("closing band: button"), max_length=80)
    band_cta_url = LinkField(_("closing band: button link"), default="/#contact")

    class Meta:
        verbose_name = _("home page")
        verbose_name_plural = _("home page")
        constraints = [SingletonModel.singleton_constraint("home_page_singleton")]

    def __str__(self):
        return str(_("Home page"))


class HeroSlide(OrderedModel, PublishableModel):
    home = models.ForeignKey(HomePage, on_delete=models.CASCADE, related_name="hero_slides")
    eyebrow = models.CharField(_("label"), max_length=80)
    title = models.CharField(_("title"), max_length=160)
    body = models.TextField(_("text"))
    cta_label = models.CharField(_("button"), max_length=60)
    cta_url = LinkField(_("button link"))
    image = models.ImageField(
        _("image"),
        upload_to=UploadTo("hero"),
        validators=image_validators,
        help_text=_("The slide's photo, or the poster frame for a video slide. 1920×1080 or larger."),
    )
    image_ar = models.ImageField(
        _("image for the Arabic site"),
        upload_to=UploadTo("hero"),
        validators=image_validators,
        blank=True,
        help_text=_("Optional — for artwork with text or direction baked in."),
    )
    video_webm = models.FileField(_("video (WebM)"), upload_to=UploadTo("hero/video"), validators=video_validators, blank=True)
    video_mp4 = models.FileField(_("video (MP4)"), upload_to=UploadTo("hero/video"), validators=video_validators, blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = _("hero slide")
        verbose_name_plural = _("hero slides")

    def __str__(self):
        return self.title

    def clean(self):
        if self.video_webm and not self.video_mp4:
            raise ValidationError({"video_mp4": _("Add an MP4 too — Safari cannot play WebM.")})


class HomeStat(OrderedModel, PublishableModel):
    """One figure in the band under the hero. A number counts up; a text value (a year,
    “24/7”) is shown as written — a year must never count up from zero."""

    home = models.ForeignKey(HomePage, on_delete=models.CASCADE, related_name="stats")
    label = models.CharField(_("label"), max_length=120)
    value = models.PositiveIntegerField(_("number"), null=True, blank=True, help_text=_("Counts up when shown."))
    prefix = models.CharField(_("prefix"), max_length=8, blank=True)
    suffix = models.CharField(_("suffix"), max_length=8, blank=True, help_text=_("e.g. + or %"))
    text = models.CharField(_("text value"), max_length=20, blank=True, help_text=_("Instead of a number, e.g. 1988 or 24/7."))

    class Meta(OrderedModel.Meta):
        verbose_name = _("figure")
        verbose_name_plural = _("figures")
        constraints = [
            models.CheckConstraint(
                condition=(Q(value__isnull=False) & Q(text="")) | (Q(value__isnull=True) & ~Q(text="")),
                name="home_stat_number_xor_text",
                violation_error_message=_("Give either a number or a text value, not both."),
            )
        ]

    def __str__(self):
        shown = self.text or f"{self.prefix}{self.value}{self.suffix}"
        return f"{shown} — {self.label}"


class HomeSectionItem(OrderedModel, PublishableModel):
    class Section(models.TextChoices):
        SERVICES = "services", _("Services cards")
        MODULES = "modules", _("Big picture list")
        STEPS = "steps", _("How-to steps")

    home = models.ForeignKey(HomePage, on_delete=models.CASCADE, related_name="section_items")
    section = models.CharField(_("section"), max_length=20, choices=Section.choices, db_index=True)
    number = models.CharField(_("number"), max_length=4, blank=True, help_text=_("Shown on steps, e.g. 01."))
    title = models.CharField(_("title"), max_length=120)
    body = models.TextField(_("text"))

    class Meta(OrderedModel.Meta):
        verbose_name = _("section item")
        verbose_name_plural = _("section items")
        ordering = ["section", "order", "id"]

    def __str__(self):
        return f"{self.get_section_display()}: {self.title}"
