from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.decorators import display

from apps.core.admin_utils import (
    ContentAdmin,
    PlainAdmin,
    SingletonAdminMixin,
    TranslatedTabularInline,
    image_tag,
    translated_fieldsets,
)

from .models import Badge, FooterColumn, NavigationItem, SiteSettings, SocialLink


@admin.register(SiteSettings)
class SiteSettingsAdmin(SingletonAdminMixin, ContentAdmin):
    readonly_fields = ["logo_light_preview", "logo_dark_preview", "favicon_preview", "updated_at"]
    fieldsets = [
        (_("Brand"), {"fields": ["short_name", "since_year", ("logo_on_light", "logo_light_preview"), ("logo_on_dark", "logo_dark_preview"), ("favicon", "favicon_preview"), "og_image"]}),
        (_("Contact"), {"fields": ["phone_display", "phone_link", "whatsapp_url", "sales_email", "careers_email", "enquiry_notification_email"]}),
        (_("Buttons and footer"), {"fields": ["primary_cta_url", "copyright_year", "updated_at"]}),
        *translated_fieldsets(
            translated=["site_name", "address", "primary_cta_label", "footer_blurb", "rights_text", "contact_heading", "contact_body", "contact_cta_label", "default_meta_title", "default_meta_description"],
        ),
    ]

    @display(description=_("Preview"))
    def logo_light_preview(self, obj):
        return image_tag(obj.logo_on_light, height=40)

    @display(description=_("Preview"))
    def logo_dark_preview(self, obj):
        return image_tag(obj.logo_on_dark, height=40)

    @display(description=_("Preview"))
    def favicon_preview(self, obj):
        return image_tag(obj.favicon, height=32)


class NavigationChildInline(TranslatedTabularInline):
    model = NavigationItem
    fk_name = "parent"
    fields = ["label", "url", "key", "is_active", "order"]
    ordering_field = "order"
    hide_ordering_field = True
    verbose_name = _("link in this group")
    verbose_name_plural = _("links in this group")


@admin.register(NavigationItem)
class NavigationItemAdmin(ContentAdmin):
    list_display = ["label", "kind", "url", "child_count", "is_active", "translation_status"]
    list_filter = ["is_active"]
    search_fields = ["label_en", "label_ar", "url", "key"]
    ordering_field = "order"
    hide_ordering_field = True
    inlines = [NavigationChildInline]
    prepopulated_fields = {"key": ["label_en"]}
    fieldsets = translated_fieldsets(
        shared=["url", "key", "is_active"],
        translated=["label"],
        extra=[(_("Placement"), {"classes": ["collapse"], "fields": ["parent", "order"]})],
    )

    def get_queryset(self, request):
        # The list shows the top level; children are edited inside their group.
        qs = super().get_queryset(request)
        if request.resolver_match and request.resolver_match.url_name.endswith("changelist"):
            qs = qs.filter(parent__isnull=True)
        return qs

    @display(description=_("Type"), label={_("Group"): "info", _("Link"): "success"})
    def kind(self, obj):
        return _("Group") if obj.is_group else _("Link")

    @display(description=_("Links"))
    def child_count(self, obj):
        return obj.children.count() or "—"


@admin.register(FooterColumn)
class FooterColumnAdmin(ContentAdmin):
    list_display = ["title", "group_list", "is_active", "translation_status"]
    ordering_field = "order"
    hide_ordering_field = True
    filter_horizontal = ["groups"]
    fieldsets = translated_fieldsets(shared=["key", "groups", "is_active"], translated=["title"])

    @display(description=_("Groups"))
    def group_list(self, obj):
        return ", ".join(g.label for g in obj.groups.all()) or "—"


@admin.register(SocialLink)
class SocialLinkAdmin(PlainAdmin):
    list_display = ["platform", "url", "is_placeholder", "is_active"]
    list_filter = ["is_active", "is_placeholder"]
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["platform", "url", "is_placeholder", "is_active"]


@admin.register(Badge)
class BadgeAdmin(ContentAdmin):
    list_display = ["thumbnail", "alt", "url", "is_active", "translation_status"]
    ordering_field = "order"
    hide_ordering_field = True
    readonly_fields = ["preview"]
    fieldsets = translated_fieldsets(shared=[("image", "preview"), "url", "is_active"], translated=["alt"])

    @display(description=_("Image"))
    def thumbnail(self, obj):
        return image_tag(obj.image, height=32)

    @display(description=_("Preview"))
    def preview(self, obj):
        return image_tag(obj.image, height=64)
