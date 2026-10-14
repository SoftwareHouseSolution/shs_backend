from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.contrib.filters.admin import RelatedDropdownFilter
from unfold.decorators import display

from apps.core.admin_utils import ContentAdmin, PlainAdmin, PublishActionsMixin, image_tag, translated_fieldsets

from .models import BusinessType, Client, Region, Sector


@admin.register(Client)
class ClientAdmin(PublishActionsMixin, PlainAdmin):
    list_display = ["thumbnail", "name", "location", "region", "sector", "placement", "is_published"]
    list_filter = [
        "is_published",
        ("region", RelatedDropdownFilter),
        ("sector", RelatedDropdownFilter),
        "business_types",
        "show_in_home_strip",
    ]
    list_filter_submit = True
    search_fields = ["name", "location", "slug"]
    list_select_related = ["region", "sector"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["region", "sector"]
    filter_horizontal = ["business_types"]
    readonly_fields = ["logo_preview"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "location", ("logo", "logo_preview"), "is_published"]}),
        (_("Classification"), {"fields": ["region", "sector", "business_types"]}),
        (_("Placement on the site"), {"fields": ["home_highlight_order", "show_in_home_strip", "featured_order"]}),
    ]

    @display(description=_("Logo"))
    def thumbnail(self, obj):
        return image_tag(obj.logo, height=28, rounded=False)

    @display(description=_("Preview"))
    def logo_preview(self, obj):
        return image_tag(obj.logo, height=64, rounded=False)

    @display(description=_("Placement"))
    def placement(self, obj):
        spots = []
        if obj.home_highlight_order is not None:
            spots.append(_("Home highlight"))
        if obj.show_in_home_strip:
            spots.append(_("Home strip"))
        if obj.featured_order is not None:
            spots.append(_("Customers strip"))
        return ", ".join(str(s) for s in spots) or "—"


class _TaxonomyAdmin(ContentAdmin):
    list_display = ["name", "key", "client_count", "translation_status"]
    search_fields = ["name_en", "name_ar", "key"]
    ordering_field = "order"
    hide_ordering_field = True
    prepopulated_fields = {"key": ["name_en"]}

    @display(description=_("Clients"))
    def client_count(self, obj):
        return obj.clients.count()


@admin.register(Region)
class RegionAdmin(_TaxonomyAdmin):
    list_display = ["name", "key", "on_map", "client_count", "translation_status"]
    fieldsets = translated_fieldsets(
        shared=["key"],
        translated=["name"],
        extra=[(_("Map"), {"fields": [("map_latitude", "map_longitude")]})],
    )

    @display(description=_("On map"), boolean=True)
    def on_map(self, obj):
        return obj.map_latitude is not None


@admin.register(Sector)
class SectorAdmin(_TaxonomyAdmin):
    fieldsets = translated_fieldsets(shared=["key"], translated=["name"])


@admin.register(BusinessType)
class BusinessTypeAdmin(_TaxonomyAdmin):
    fieldsets = translated_fieldsets(shared=["key"], translated=["name"])
