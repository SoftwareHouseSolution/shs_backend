"""Site-wide content: settings, the navigation tree, footer columns, social links, badges.

Everything here is needed by every page, so the API serves it in one response
(GET /api/v1/site/) that the frontend layout fetches once.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from apps.core.media import LinkField, UploadTo
from apps.core.models import OrderedModel, SingletonModel, TimeStampedModel
from apps.core.validators import icon_validators, image_validators, logo_validators


class SiteSettings(SingletonModel, TimeStampedModel):
    # Brand
    site_name = models.CharField(_("site name"), max_length=120)
    short_name = models.CharField(_("short name"), max_length=20, blank=True)
    since_year = models.PositiveSmallIntegerField(
        _("established"), validators=[MinValueValidator(1900), MaxValueValidator(2100)]
    )
    logo_on_light = models.FileField(
        _("logo for light backgrounds"),
        upload_to=UploadTo("brand"),
        validators=logo_validators,
        blank=True,
        help_text=_("Optional. Leave empty to use the built-in SWH lockup."),
    )
    logo_on_dark = models.FileField(
        _("logo for dark backgrounds"),
        upload_to=UploadTo("brand"),
        validators=logo_validators,
        blank=True,
        help_text=_("Optional. Shown over the hero photography."),
    )
    favicon = models.FileField(
        _("favicon"), upload_to=UploadTo("brand"), validators=icon_validators, blank=True
    )
    # Contact
    phone_display = models.CharField(_("phone (as displayed)"), max_length=40)
    phone_link = models.CharField(
        _("phone (for dialling)"),
        max_length=20,
        validators=[RegexValidator(r"^\+?[0-9]{6,15}$", _("Digits only, with country code, e.g. +201558856988."))],
    )
    whatsapp_url = models.URLField(_("WhatsApp link"), help_text=_("e.g. https://wa.me/201558856988"))
    sales_email = models.EmailField(_("sales e-mail"))
    careers_email = models.EmailField(_("careers e-mail"))
    address = models.CharField(_("address"), max_length=255)
    # Calls to action and footer
    primary_cta_label = models.CharField(_("primary button label"), max_length=60)
    primary_cta_url = LinkField(
        _("primary button link"), help_text=_("e.g. /#contact — the navbar's main button.")
    )
    footer_blurb = models.TextField(_("footer text"), help_text=_("The year established is appended."))
    copyright_year = models.CharField(_("copyright year"), max_length=9)
    rights_text = models.CharField(_("rights text"), max_length=80)
    # Contact section (home page and Customers page)
    contact_heading = models.CharField(_("contact section: heading"), max_length=160, default="")
    contact_body = models.TextField(_("contact section: text"), default="")
    contact_cta_label = models.CharField(_("contact section: WhatsApp button"), max_length=80, default="")
    # SEO
    default_meta_title = models.CharField(_("default page title"), max_length=70)
    default_meta_description = models.CharField(_("default meta description"), max_length=300)
    og_image = models.ImageField(
        _("default social share image"),
        upload_to=UploadTo("seo"),
        validators=image_validators,
        blank=True,
        help_text=_("1200×630 recommended."),
    )
    # Operations
    enquiry_notification_email = models.EmailField(
        _("send enquiries to"),
        blank=True,
        help_text=_("Where new website enquiries are e-mailed. Falls back to the server setting."),
    )
    review_share_url = models.URLField(
        _("Facebook post for reviews"),
        blank=True,
        help_text=_(
            "After sending a review, clients are offered to post it here too (e.g. the Ahl El-Sagha group post). "
            "Leave empty to hide that step."
        ),
    )

    class Meta:
        verbose_name = _("site settings")
        verbose_name_plural = _("site settings")
        constraints = [SingletonModel.singleton_constraint("site_settings_singleton")]

    def __str__(self):
        return str(_("Site settings"))


class NavigationItem(OrderedModel):
    """One entry in the two-level navigation tree.

    A top-level item is either a link (has a URL) or a dropdown group (no URL, has
    children). Children are always links. The footer reuses groups by `key`.
    """

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        limit_choices_to={"parent__isnull": True},
        verbose_name=_("parent group"),
    )
    key = models.SlugField(
        _("key"),
        max_length=60,
        unique=True,
        help_text=_("Stable identifier used in the page markup. Not shown to visitors."),
    )
    label = models.CharField(_("label"), max_length=80)
    url = LinkField(_("link"), blank=True, help_text=_("Leave empty for a dropdown group."))
    is_active = models.BooleanField(_("active"), default=True)

    class Meta(OrderedModel.Meta):
        verbose_name = _("navigation item")
        verbose_name_plural = _("navigation")
        constraints = [
            # Children are always links.
            models.CheckConstraint(
                condition=Q(parent__isnull=True) | ~Q(url=""), name="nav_child_has_url"
            ),
            models.CheckConstraint(condition=~Q(parent=F("pk")), name="nav_not_own_parent"),
        ]

    def __str__(self):
        return f"{self.parent.label} › {self.label}" if self.parent_id else self.label

    @property
    def is_group(self) -> bool:
        return self.parent_id is None and not self.url

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": _("An item cannot be its own parent.")})
            if self.parent.parent_id:
                raise ValidationError({"parent": _("Navigation has two levels; choose a top-level group.")})
            if self.parent.url:
                raise ValidationError({"parent": _("The chosen parent is a link, not a dropdown group.")})
            if not self.url:
                raise ValidationError({"url": _("Items inside a group need a link.")})
        elif self.pk and self.url and self.children.exists():
            raise ValidationError({"url": _("A group with children cannot also be a link.")})


class FooterColumn(OrderedModel):
    key = models.SlugField(_("key"), max_length=60, unique=True)
    title = models.CharField(_("heading"), max_length=60)
    groups = models.ManyToManyField(
        NavigationItem,
        related_name="footer_columns",
        limit_choices_to={"parent__isnull": True, "url": ""},
        verbose_name=_("navigation groups"),
        help_text=_("The column lists every link inside these groups, in menu order."),
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta(OrderedModel.Meta):
        verbose_name = _("footer column")
        verbose_name_plural = _("footer columns")

    def __str__(self):
        return self.title


class SocialLink(OrderedModel):
    class Platform(models.TextChoices):
        # Each value must have a glyph in the frontend's SocialIcon component.
        LINKEDIN = "linkedin", "LinkedIn"
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"

    platform = models.CharField(_("platform"), max_length=20, choices=Platform.choices, unique=True)
    url = models.URLField(_("profile URL"))
    is_placeholder = models.BooleanField(
        _("placeholder"),
        default=False,
        help_text=_("Tick while the URL is a stand-in, so it is easy to find and replace."),
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta(OrderedModel.Meta):
        verbose_name = _("social link")
        verbose_name_plural = _("social links")

    def __str__(self):
        return self.get_platform_display()


class Badge(OrderedModel):
    """A certification or partner mark shown in the navbar. Only add credentials the company
    actually holds — a badge asserts a qualification."""

    image = models.FileField(_("image"), upload_to=UploadTo("badges"), validators=logo_validators)
    alt = models.CharField(_("description"), max_length=160, help_text=_("Read aloud by screen readers."))
    url = models.URLField(_("verification link"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta(OrderedModel.Meta):
        verbose_name = _("badge")
        verbose_name_plural = _("badges")

    def __str__(self):
        return self.alt
