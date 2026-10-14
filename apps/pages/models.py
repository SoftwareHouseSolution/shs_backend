"""Interior pages, built from an ordered list of typed content blocks.

A block's `kind` decides which of its fields matter and how it is rendered — see
apps/pages/blocks.py, where each kind is a strategy that validates and serialises itself.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.media import LinkField, UploadTo
from apps.core.models import OrderedModel, PublishableModel, TimeStampedModel
from apps.core.validators import image_validators, logo_validators, video_validators


class Page(OrderedModel, PublishableModel, TimeStampedModel):
    class Template(models.TextChoices):
        STANDARD = "standard", _("Standard — header and content blocks")
        CUSTOMERS = "customers", _("Customers — header, client map and contact")

    slug = models.SlugField(
        _("slug"),
        max_length=80,
        unique=True,
        help_text=_("The page's address: /en/<slug> and /ar/<slug>. Changing it breaks existing links."),
    )
    template = models.CharField(_("template"), max_length=20, choices=Template.choices, default=Template.STANDARD)
    title = models.CharField(_("title"), max_length=120)
    eyebrow = models.CharField(_("label above the title"), max_length=60)
    lede = models.CharField(_("introduction"), max_length=300)
    header_image = models.ImageField(_("header image"), upload_to=UploadTo("pages"), validators=image_validators)
    meta_title = models.CharField(_("SEO title"), max_length=70, blank=True, help_text=_("Defaults to the title."))
    meta_description = models.CharField(_("meta description"), max_length=300)

    # Optional intro video (used by the Customers template as a modal on arrival).
    video_desktop = models.FileField(_("video (landscape)"), upload_to=UploadTo("pages/video"), validators=video_validators, blank=True)
    video_mobile = models.FileField(_("video (portrait)"), upload_to=UploadTo("pages/video"), validators=video_validators, blank=True)
    video_poster_desktop = models.ImageField(_("poster (landscape)"), upload_to=UploadTo("pages/video"), validators=image_validators, blank=True)
    video_poster_mobile = models.ImageField(_("poster (portrait)"), upload_to=UploadTo("pages/video"), validators=image_validators, blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = _("page")
        verbose_name_plural = _("pages")

    def __str__(self):
        return self.title

    @property
    def path(self) -> str:
        return f"/{self.slug}"

    def clean(self):
        if self.video_mobile and not self.video_desktop:
            raise ValidationError({"video_desktop": _("Add the landscape video; the portrait one is optional.")})


class PageBlock(OrderedModel):
    class Kind(models.TextChoices):
        INTRO = "intro", _("Introduction — label, heading, text")
        CARDS = "cards", _("Cards — a grid of titled cards")
        NUMBERED = "numbered", _("Numbered list")
        STEPS = "steps", _("Steps — numbered cards")
        LOGOS = "logos", _("Partner logos")
        HARDWARE = "hardware", _("Hardware tiles — image cards")
        SPEC = "spec", _("Comparison table")
        TIMELINE = "timeline", _("Events timeline")
        GALLERY = "gallery", _("Photo gallery (from an event)")
        TESTIMONIALS = "testimonials", _("Testimonials")
        CTA = "cta", _("Call to action")

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="blocks")
    kind = models.CharField(_("type"), max_length=20, choices=Kind.choices)
    is_visible = models.BooleanField(_("visible"), default=True)

    eyebrow = models.CharField(_("label"), max_length=80, blank=True)
    heading = models.CharField(_("heading"), max_length=200, blank=True)
    body = models.TextField(_("text"), blank=True)
    label = models.CharField(
        _("button / caption"), max_length=120, blank=True, help_text=_("Button text (CTA) or caption (logos).")
    )
    url = LinkField(_("button link"), blank=True)

    comparison_table = models.ForeignKey(
        "content.ComparisonTable",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="page_blocks",
        verbose_name=_("comparison table"),
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="page_blocks",
        verbose_name=_("event (gallery source)"),
    )
    partner_category = models.CharField(
        _("partner category"),
        max_length=20,
        blank=True,
        choices=[("technology", _("Technology partners")), ("business", _("Business partners"))],
    )

    class Meta(OrderedModel.Meta):
        verbose_name = _("content block")
        verbose_name_plural = _("content blocks")
        indexes = [models.Index(fields=["page", "order"], name="pageblock_page_order")]

    def __str__(self):
        return f"{self.get_kind_display().split(' —')[0]}: {self.heading or self.label or self.page.title}"

    def clean(self):
        from .blocks import strategy_for

        errors = strategy_for(self.kind).validate(self)
        if errors:
            raise ValidationError(errors)


class BlockItem(OrderedModel):
    """A card, list entry, step or tile inside a block."""

    block = models.ForeignKey(PageBlock, on_delete=models.CASCADE, related_name="items")
    number = models.CharField(_("number"), max_length=4, blank=True, help_text=_("e.g. 01, for steps and tiles."))
    title = models.CharField(_("title"), max_length=160)
    body = models.TextField(_("text"), blank=True)
    image = models.FileField(_("image"), upload_to=UploadTo("pages/items"), validators=logo_validators, blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = _("item")
        verbose_name_plural = _("items")

    def __str__(self):
        return self.title
