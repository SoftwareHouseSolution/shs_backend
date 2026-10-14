"""Builds the home page payload from the HomePage record and the collections it draws on
(clients, events, testimonials, a comparison table).

A facade over several apps' selectors: the view asks for "the home page" and does not need
to know which apps contribute to it.
"""

from django.db.models import Prefetch

from apps.clients import selectors as clients
from apps.clients.serializers import ClientLogoSerializer
from apps.content import selectors as content
from apps.content.serializers import TestimonialSerializer
from apps.core.media import absolute_media_url
from apps.events import selectors as events
from apps.events.serializers import EventSummarySerializer

from .models import HeroSlide, HomePage, HomeSectionItem, HomeStat
from .serializers import HeroSlideSerializer, HomeStatSerializer, SectionItemSerializer

HOME_EVENTS_LIMIT = 6


def _load_home() -> HomePage:
    return (
        HomePage.objects.select_related("specs_table")
        .prefetch_related(
            Prefetch("hero_slides", queryset=HeroSlide.objects.published().order_by("order", "id")),
            Prefetch("stats", queryset=HomeStat.objects.published().order_by("order", "id")),
            Prefetch("section_items", queryset=HomeSectionItem.objects.published().order_by("order", "id")),
        )
        .get(pk=HomePage.SINGLETON_PK)
    )


def build_home_payload(request) -> dict:
    home = _load_home()
    ctx = {"request": request}
    items = {section: [] for section in HomeSectionItem.Section.values}
    for item in home.section_items.all():
        items[item.section].append(item)

    def section(key):
        return SectionItemSerializer(items[key], many=True).data

    specs = None
    if home.specs_table_id:
        table = content.comparison_table_queryset().get(pk=home.specs_table_id)
        specs = {"eyebrow": home.specs_eyebrow, "heading": home.specs_heading, **table.as_grid()}

    testimonial = content.featured_testimonial()

    return {
        "seo": {"meta_title": home.meta_title or None, "meta_description": home.meta_description or None},
        "hero": HeroSlideSerializer(home.hero_slides.all(), many=True, context=ctx).data,
        "figures": {
            "eyebrow": home.figures_eyebrow,
            "aria_label": home.figures_aria_label,
            "stats": HomeStatSerializer(home.stats.all(), many=True).data,
        },
        "proof": {
            "lede": home.proof_lede,
            "strip_aria_label": home.proof_strip_aria_label,
            "cta": {"label": home.proof_cta_label, "url": home.proof_cta_url},
            "highlighted": ClientLogoSerializer(clients.home_highlighted_clients(), many=True, context=ctx).data,
            "strip": ClientLogoSerializer(clients.home_strip_clients(), many=True, context=ctx).data,
        },
        "services": {
            "eyebrow": home.services_eyebrow,
            "heading": home.services_heading,
            "body": home.services_body,
            "image": absolute_media_url(home.services_image, request),
            "image_alt": home.services_image_alt,
            "items": section(HomeSectionItem.Section.SERVICES),
        },
        "big_picture": {
            "heading": home.big_picture_heading,
            "body": home.big_picture_body,
            "image": absolute_media_url(home.big_picture_image, request),
            "image_alt": home.big_picture_image_alt,
            "items": section(HomeSectionItem.Section.MODULES),
        },
        "discover_more_label": home.discover_more_label,
        "specs": specs,
        "testimonial": TestimonialSerializer(testimonial, context=ctx).data if testimonial else None,
        "how_to": {
            "heading": home.how_to_heading,
            "cta": {"label": home.discover_more_label, "url": "#contact"},
            "items": section(HomeSectionItem.Section.STEPS),
        },
        "events": {
            "eyebrow": home.events_eyebrow,
            "heading": home.events_heading,
            "body": home.events_body,
            "cta": {"label": home.events_cta_label, "url": home.events_cta_url},
            "items": EventSummarySerializer(
                events.published_events()[:HOME_EVENTS_LIMIT], many=True, context=ctx
            ).data,
        },
        "band": {
            "heading": home.band_heading,
            "body": home.band_body,
            "cta": {"label": home.band_cta_label, "url": home.band_cta_url},
        },
    }

