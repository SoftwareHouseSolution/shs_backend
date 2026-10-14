from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from unfold.admin import TabularInline
from unfold.decorators import display

from apps.core.admin_utils import (
    ContentAdmin,
    PlainAdmin,
    PublishActionsMixin,
    TranslatedTabularInline,
    image_tag,
    translated_fieldsets,
)

from .models import ComparisonCell, ComparisonColumn, ComparisonRow, ComparisonTable, Partner, Testimonial


class ComparisonColumnInline(TranslatedTabularInline):
    model = ComparisonColumn
    fields = ["label", "highlight", "order"]
    ordering_field = "order"
    hide_ordering_field = True


class ComparisonCellInline(TranslatedTabularInline):
    model = ComparisonCell
    fields = ["column", "ok", "text"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Offer only this table's columns.
        if db_field.name == "column":
            row_id = request.resolver_match.kwargs.get("object_id")
            row = ComparisonRow.objects.filter(pk=row_id).first()
            if row:
                kwargs["queryset"] = ComparisonColumn.objects.filter(table=row.table)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ComparisonRowInline(TabularInline):
    """Rows are listed on the table with a link to edit their cells."""

    model = ComparisonRow
    fields = ["order", "summary"]
    readonly_fields = ["summary"]
    extra = 0
    show_change_link = True

    @display(description=_("Cells"))
    def summary(self, obj):
        if not obj.pk:
            return "—"
        return format_html_join(
            " · ", "{} {}", ((("✓" if c.ok else "✗"), c.text) for c in obj.cells.all())
        )


@admin.register(ComparisonTable)
class ComparisonTableAdmin(PlainAdmin):
    list_display = ["name", "key", "column_count", "row_count", "updated_at"]
    search_fields = ["name", "key"]
    prepopulated_fields = {"key": ["name"]}
    fields = ["name", "key", "preview"]
    readonly_fields = ["preview"]
    inlines = [ComparisonColumnInline, ComparisonRowInline]

    @display(description=_("Columns"))
    def column_count(self, obj):
        return obj.columns.count()

    @display(description=_("Rows"))
    def row_count(self, obj):
        return obj.rows.count()

    @display(description=_("Preview"))
    def preview(self, obj):
        if not obj.pk:
            return "—"
        grid = obj.as_grid()
        head = format_html_join("", "<th style='padding:4px 10px;text-align:start'>{}</th>", ((c["label"],) for c in grid["columns"]))
        body = format_html_join(
            "",
            "<tr>{}</tr>",
            (
                (format_html_join("", "<td style='padding:4px 10px'>{} {}</td>", (("✓" if c["ok"] else "✗", c["text"]) for c in r["cells"])),)
                for r in grid["rows"]
            ),
        )
        return format_html("<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>", head, body)


@admin.register(ComparisonRow)
class ComparisonRowAdmin(PlainAdmin):
    list_display = ["__str__", "table", "order"]
    list_filter = ["table"]
    fields = ["table", "order"]
    inlines = [ComparisonCellInline]

    def get_model_perms(self, request):
        # Reached from the table page; hidden from the sidebar and the app index.
        return {}


@admin.register(Testimonial)
class TestimonialAdmin(PublishActionsMixin, ContentAdmin):
    list_display = ["thumbnail", "author_name", "author_company", "is_featured", "is_published", "translation_status"]
    list_filter = ["is_published", "is_featured"]
    search_fields = ["author_name_en", "author_name_ar", "author_company_en", "quote_en", "quote_ar"]
    ordering_field = "order"
    hide_ordering_field = True
    fieldsets = translated_fieldsets(
        shared=["avatar", "is_featured", "is_published"],
        translated=["quote", "author_name", "author_company"],
    )

    @display(description=_("Photo"))
    def thumbnail(self, obj):
        return image_tag(obj.avatar, height=36)


@admin.register(Partner)
class PartnerAdmin(PlainAdmin):
    list_display = ["thumbnail", "name", "category", "website", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["name"]
    ordering_field = "order"
    hide_ordering_field = True
    readonly_fields = ["logo_preview"]
    fields = ["name", ("logo", "logo_preview"), "website", "category", "is_active"]

    @display(description=_("Logo"))
    def thumbnail(self, obj):
        return image_tag(obj.logo, height=28, rounded=False)

    @display(description=_("Preview"))
    def logo_preview(self, obj):
        return image_tag(obj.logo, height=56, rounded=False)
