"""The client roster and the lookups it is filtered by."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.media import UploadTo
from apps.core.models import OrderedModel, PublishableModel, TimeStampedModel
from apps.core.validators import logo_validators


class Region(OrderedModel):
    """A filtering bucket for the client map. Regions with coordinates get a pin on the
    map; regions without (International, Nationwide) are listed as chips beneath it."""

    key = models.SlugField(_("key"), max_length=60, unique=True)
    name = models.CharField(_("name"), max_length=80)
    map_latitude = models.DecimalField(
        _("map pin latitude"),
        max_digits=8,
        decimal_places=5,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text=_("Where the region's label sits on the map. Leave both empty for no pin."),
    )
    map_longitude = models.DecimalField(
        _("map pin longitude"),
        max_digits=8,
        decimal_places=5,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    class Meta(OrderedModel.Meta):
        verbose_name = _("region")
        verbose_name_plural = _("regions")
        constraints = [
            models.CheckConstraint(
                condition=Q(map_latitude__isnull=True, map_longitude__isnull=True)
                | Q(map_latitude__isnull=False, map_longitude__isnull=False),
                name="region_pin_complete",
                violation_error_message=_("Give both latitude and longitude, or neither."),
            )
        ]

    def __str__(self):
        return self.name


class Sector(OrderedModel):
    key = models.SlugField(_("key"), max_length=60, unique=True)
    name = models.CharField(_("name"), max_length=80)

    class Meta(OrderedModel.Meta):
        verbose_name = _("sector")
        verbose_name_plural = _("sectors")

    def __str__(self):
        return self.name


class BusinessType(OrderedModel):
    key = models.SlugField(_("key"), max_length=60, unique=True)
    name = models.CharField(_("name"), max_length=80)

    class Meta(OrderedModel.Meta):
        verbose_name = _("business type")
        verbose_name_plural = _("business types")

    def __str__(self):
        return self.name


class Client(PublishableModel, TimeStampedModel):
    """One business on the roster.

    `name` and `location` are NOT translated on purpose: they are proper nouns taken
    verbatim from the company profile, and transliterating them would invent spellings the
    businesses themselves do not use.
    """

    slug = models.SlugField(_("slug"), max_length=120, unique=True)
    name = models.CharField(_("name"), max_length=160, db_index=True)
    location = models.CharField(_("location"), max_length=160, blank=True)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="clients", verbose_name=_("region"))
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, related_name="clients", verbose_name=_("sector"))
    business_types = models.ManyToManyField(
        BusinessType, related_name="clients", blank=True, verbose_name=_("business types")
    )
    logo = models.FileField(_("logo"), upload_to=UploadTo("clients"), validators=logo_validators)

    # Placement on the site
    home_highlight_order = models.PositiveSmallIntegerField(
        _("home page highlight position"),
        null=True,
        blank=True,
        help_text=_("Shown large and still above the home page logo strip. Leave empty to not highlight."),
    )
    show_in_home_strip = models.BooleanField(
        _("in the home page logo strip"), default=False, db_index=True
    )
    featured_order = models.PositiveSmallIntegerField(
        _("customers page strip position"),
        null=True,
        blank=True,
        help_text=_("Position in the featured strip on the Customers page. Leave empty to leave out."),
    )

    class Meta:
        verbose_name = _("client")
        verbose_name_plural = _("clients")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_published", "name"], name="client_published_name"),
            models.Index(fields=["region", "name"], name="client_region_name"),
        ]

    def __str__(self):
        return self.name
