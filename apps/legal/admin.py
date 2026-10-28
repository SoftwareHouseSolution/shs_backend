"""Admin → Site → Legal pages: the privacy policy, with its own on/off switch."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.decorators import display

from apps.core.admin_utils import ContentAdmin, translated_fieldsets

from .models import LegalDocument


@admin.register(LegalDocument)
class LegalDocumentAdmin(ContentAdmin):
    list_display = ["title", "slug", "last_updated", "is_published", "show_in_footer", "translation_status", "address"]
    list_editable = ["is_published", "show_in_footer"]
    readonly_fields = ["updated_at"]
    fieldsets = translated_fieldsets(
        shared=["slug", "last_updated", "is_published", "show_in_footer", "updated_at"],
        translated=["title", "body"],
    )

    @display(description=_("Address"))
    def address(self, obj):
        return f"/ar/{obj.slug} · /en/{obj.slug}"
