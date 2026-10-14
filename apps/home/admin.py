from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.core.admin_utils import (
    LANGUAGE_TABS,
    ContentAdmin,
    SingletonAdminMixin,
    TranslatedStackedInline,
    TranslatedTabularInline,
)

from .models import HeroSlide, HomePage, HomeSectionItem, HomeStat
from .translation import HOME_TRANSLATED_FIELDS


class HeroSlideInline(TranslatedStackedInline):
    model = HeroSlide
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    fields = [
        "image",
        "image_ar",
        ("video_mp4", "video_webm"),
        "cta_url",
        "is_published",
        *[f"{f}_{code}" for code, _l in LANGUAGE_TABS for f in ("eyebrow", "title", "body", "cta_label")],
        "order",
    ]


class HomeStatInline(TranslatedTabularInline):
    model = HomeStat
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["label", "value", "prefix", "suffix", "text", "is_published", "order"]


class HomeSectionItemInline(TranslatedTabularInline):
    model = HomeSectionItem
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["section", "number", "title", "body", "is_published", "order"]


# Section → (fields shown in the shared area). Translated copy is grouped per language tab.
_SECTIONS = [
    (_("Figures"), ["figures_eyebrow", "figures_aria_label"]),
    (_("Client band"), ["proof_lede", "proof_strip_aria_label", "proof_cta_label"]),
    (_("Services"), ["services_eyebrow", "services_heading", "services_body", "services_image_alt"]),
    (_("Big picture"), ["big_picture_heading", "big_picture_body", "big_picture_image_alt", "discover_more_label"]),
    (_("Comparison"), ["specs_eyebrow", "specs_heading"]),
    (_("How-to"), ["how_to_heading"]),
    (_("Events"), ["events_eyebrow", "events_heading", "events_body", "events_cta_label"]),
    (_("Closing band"), ["band_heading", "band_body", "band_cta_label"]),
    (_("SEO"), ["meta_title", "meta_description"]),
]
assert {f for _t, fs in _SECTIONS for f in fs} == set(HOME_TRANSLATED_FIELDS)


@admin.register(HomePage)
class HomePageAdmin(SingletonAdminMixin, ContentAdmin):
    inlines = [HeroSlideInline, HomeStatInline, HomeSectionItemInline]
    readonly_fields = ["updated_at"]

    def get_fieldsets(self, request, obj=None):
        shared = (
            _("Images, links and tables"),
            {
                "fields": [
                    "services_image",
                    "big_picture_image",
                    "specs_table",
                    "proof_cta_url",
                    "events_cta_url",
                    "band_cta_url",
                    "updated_at",
                ]
            },
        )
        tabs = [
            (label, {"classes": ["tab"], "fields": [f"{f}_{code}" for _t, fs in _SECTIONS for f in fs]})
            for code, label in LANGUAGE_TABS
        ]
        return [shared, *tabs]
