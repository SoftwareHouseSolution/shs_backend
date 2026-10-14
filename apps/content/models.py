"""Content reused across pages: comparison tables, testimonials, partners."""

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.media import UploadTo
from apps.core.models import OrderedModel, PublishableModel, TimeStampedModel
from apps.core.validators import image_validators, logo_validators


class ComparisonTable(TimeStampedModel):
    """A ticks-and-crosses table ("Why choose SWH?"). Referenced by the home page and by
    `spec` blocks on interior pages, so one table can be shown in several places."""

    key = models.SlugField(_("key"), max_length=80, unique=True)
    name = models.CharField(
        _("internal name"), max_length=120, help_text=_("For editors only; not shown on the site.")
    )

    class Meta:
        verbose_name = _("comparison table")
        verbose_name_plural = _("comparison tables")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def as_grid(self) -> dict:
        """Columns and rows with cells aligned to the column order. Missing cells render as
        an empty cross so a half-filled row cannot shift the others."""
        columns = list(self.columns.all())
        rows = []
        for row in self.rows.all():
            by_column = {cell.column_id: cell for cell in row.cells.all()}
            rows.append(
                {
                    "cells": [
                        {"ok": by_column[c.id].ok, "text": by_column[c.id].text}
                        if c.id in by_column
                        else {"ok": False, "text": ""}
                        for c in columns
                    ]
                }
            )
        return {
            "columns": [{"label": c.label, "highlight": c.highlight} for c in columns],
            "rows": rows,
        }


class ComparisonColumn(OrderedModel):
    table = models.ForeignKey(ComparisonTable, on_delete=models.CASCADE, related_name="columns")
    label = models.CharField(_("label"), max_length=80)
    highlight = models.BooleanField(_("highlight"), default=False, help_text=_("SWH's own column."))

    class Meta(OrderedModel.Meta):
        verbose_name = _("column")
        verbose_name_plural = _("columns")

    def __str__(self):
        return self.label


class ComparisonRow(OrderedModel):
    table = models.ForeignKey(ComparisonTable, on_delete=models.CASCADE, related_name="rows")

    class Meta(OrderedModel.Meta):
        verbose_name = _("row")
        verbose_name_plural = _("rows")

    def __str__(self):
        first = self.cells.order_by("column__order").first()
        return first.text if first else str(_("Row %(n)s") % {"n": self.order + 1})


class ComparisonCell(models.Model):
    row = models.ForeignKey(ComparisonRow, on_delete=models.CASCADE, related_name="cells")
    column = models.ForeignKey(ComparisonColumn, on_delete=models.CASCADE, related_name="cells")
    ok = models.BooleanField(_("tick"), default=False, help_text=_("Tick (✓) or cross (✗)."))
    text = models.CharField(_("text"), max_length=160)

    class Meta:
        verbose_name = _("cell")
        verbose_name_plural = _("cells")
        ordering = ["column__order", "column_id"]
        constraints = [models.UniqueConstraint(fields=["row", "column"], name="comparison_cell_unique")]

    def __str__(self):
        return self.text

    def clean(self):
        if self.row_id and self.column_id and self.row.table_id != self.column.table_id:
            raise ValidationError({"column": _("This column belongs to a different table.")})


class Testimonial(OrderedModel, PublishableModel, TimeStampedModel):
    quote = models.TextField(_("quote"))
    author_name = models.CharField(_("author"), max_length=120)
    author_company = models.CharField(_("company"), max_length=120, blank=True)
    avatar = models.ImageField(_("photo or logo"), upload_to=UploadTo("testimonials"), validators=image_validators, blank=True)
    is_featured = models.BooleanField(
        _("featured on the home page"),
        default=False,
        help_text=_("Only one testimonial can be featured; featuring this one un-features the other."),
    )

    class Meta(OrderedModel.Meta):
        verbose_name = _("testimonial")
        verbose_name_plural = _("testimonials")
        constraints = [
            models.UniqueConstraint(
                fields=["is_featured"], condition=Q(is_featured=True), name="single_featured_testimonial"
            )
        ]

    def __str__(self):
        return f"{self.author_name} — {self.author_company}" if self.author_company else self.author_name

    @property
    def attribution(self) -> str:
        return str(self)

    def save(self, *args, **kwargs):
        # Featuring is exclusive: un-feature the previous one in the same transaction so
        # the partial unique constraint never sees two.
        with transaction.atomic():
            if self.is_featured:
                Testimonial.objects.filter(is_featured=True).exclude(pk=self.pk).update(is_featured=False)
            super().save(*args, **kwargs)


class Partner(OrderedModel, TimeStampedModel):
    class Category(models.TextChoices):
        TECHNOLOGY = "technology", _("Technology partner")
        BUSINESS = "business", _("Business partner")

    name = models.CharField(_("name"), max_length=120, help_text=_("A company name — not translated."))
    logo = models.FileField(_("logo"), upload_to=UploadTo("partners"), validators=logo_validators)
    website = models.URLField(_("website"), blank=True)
    category = models.CharField(_("category"), max_length=20, choices=Category.choices, default=Category.TECHNOLOGY, db_index=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta(OrderedModel.Meta):
        verbose_name = _("partner")
        verbose_name_plural = _("partners")

    def __str__(self):
        return self.name
