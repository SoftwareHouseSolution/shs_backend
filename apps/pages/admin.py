from django import forms
from django.contrib import admin
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.decorators import display

from apps.core.admin_utils import (
    LANGUAGE_TABS,
    ContentAdmin,
    PublishActionsMixin,
    TranslatedTabularInline,
    translated_fieldsets,
)

from .models import BlockItem, Page, PageBlock

# Which fields each block type uses. Drives the conditional display in the block form, so
# an editor only sees the inputs that matter for the type they picked.
_SHOW_WHEN = {
    "eyebrow": "kind == 'intro'",
    "heading": "!['timeline', 'logos'].includes(kind)",
    "body": "['intro', 'cta'].includes(kind)",
    "label": "['logos', 'cta'].includes(kind)",
    "url": "kind == 'cta'",
    "comparison_table": "kind == 'spec'",
    "event": "kind == 'gallery'",
    "partner_category": "kind == 'logos'",
}
_TRANSLATED = ("eyebrow", "heading", "body", "label")


def _conditional_fields() -> dict[str, str]:
    out = {}
    for name, expr in _SHOW_WHEN.items():
        if name in _TRANSLATED:
            for code, _label in LANGUAGE_TABS:
                out[f"{name}_{code}"] = expr
        else:
            out[name] = expr
    return out


class ContainedErrorsForm(forms.ModelForm):
    """A model's clean() may report errors on fields this (inline) form does not show;
    Django would raise ValueError for those. Show them as form-level errors instead."""

    def _update_errors(self, errors):
        if hasattr(errors, "error_dict"):
            remapped: dict[str, list] = {}
            for field, messages in errors.error_dict.items():
                key = field if field in self.fields else NON_FIELD_ERRORS
                if key == NON_FIELD_ERRORS and field != NON_FIELD_ERRORS:
                    messages = [ValidationError(f"{field}: {m.message}", params=m.params) for m in messages]
                remapped.setdefault(key, []).extend(messages)
            errors = ValidationError(remapped)
        super()._update_errors(errors)


class PageBlockInline(TranslatedTabularInline):
    """Overview and ordering on the page form. Each block's content is edited on its own
    form ("change" link), which shows only the fields its type uses."""

    model = PageBlock
    form = ContainedErrorsForm
    fields = ["kind", "summary", "is_visible", "order"]
    readonly_fields = ["kind", "summary"]
    ordering_field = "order"
    hide_ordering_field = True
    show_change_link = True
    tab = True

    def has_add_permission(self, request, obj=None):
        return False

    @display(description=_("Content"))
    def summary(self, obj):
        return obj.heading or obj.label or "—"


@admin.register(Page)
class PageAdmin(PublishActionsMixin, ContentAdmin):
    list_display = ["title", "slug", "template", "block_count", "is_published", "translation_status", "updated_at"]
    list_filter = ["is_published", "template"]
    search_fields = ["title_en", "title_ar", "slug"]
    ordering_field = "order"
    hide_ordering_field = True
    prepopulated_fields = {"slug": ["title_en"]}
    readonly_fields = ["add_block_link", "updated_at"]
    inlines = [PageBlockInline]
    fieldsets = translated_fieldsets(
        shared=[
            "slug",
            "template",
            "header_image",
            "is_published",
            "add_block_link",
            "updated_at",
        ],
        translated=["title", "eyebrow", "lede", "meta_title", "meta_description"],
        extra=[
            (
                _("Intro video (Customers template)"),
                {"classes": ["collapse"], "fields": ["video_desktop", "video_mobile", "video_poster_desktop", "video_poster_mobile"]},
            )
        ],
    )

    @display(description=_("Blocks"))
    def block_count(self, obj):
        return obj.blocks.count()

    @display(description=_("Content blocks"))
    def add_block_link(self, obj):
        if not obj.pk:
            return _("Save the page first, then add blocks.")
        url = reverse("admin:pages_pageblock_add") + f"?page={obj.pk}&order={obj.blocks.count()}"
        return format_html('<a class="text-primary-600 font-medium" href="{}">+ {}</a>', url, _("Add a content block"))


class BlockItemInline(TranslatedTabularInline):
    model = BlockItem
    fields = ["number", "title", "body", "image", "order"]
    ordering_field = "order"
    hide_ordering_field = True
    verbose_name_plural = _("items (cards, list entries, steps, tiles)")


@admin.register(PageBlock)
class PageBlockAdmin(ContentAdmin):
    list_display = ["__str__", "page", "kind", "is_visible", "translation_status"]
    list_filter = ["kind", "page", "is_visible"]
    search_fields = ["heading_en", "heading_ar", "page__title_en"]
    autocomplete_fields = ["page", "event"]
    inlines = [BlockItemInline]
    conditional_fields = _conditional_fields()
    fieldsets = translated_fieldsets(
        shared=["page", "kind", "is_visible", "order", "url", "comparison_table", "event", "partner_category"],
        translated=list(_TRANSLATED),
    )

    def get_model_perms(self, request):
        # Reached from its page; kept out of the sidebar and the app index.
        return {}

    def response_post_save_change(self, request, obj):
        return self._back_to_page(obj) or super().response_post_save_change(request, obj)

    def response_post_save_add(self, request, obj):
        return self._back_to_page(obj) or super().response_post_save_add(request, obj)

    @staticmethod
    def _back_to_page(obj):
        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(reverse("admin:pages_page_change", args=[obj.page_id]) + "#content-blocks")
