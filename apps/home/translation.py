from modeltranslation.translator import TranslationOptions, register

from .models import HeroSlide, HomePage, HomeSectionItem, HomeStat

HOME_TRANSLATED_FIELDS = (
    "meta_title",
    "meta_description",
    "figures_eyebrow",
    "figures_aria_label",
    "proof_lede",
    "proof_strip_aria_label",
    "proof_cta_label",
    "services_eyebrow",
    "services_heading",
    "services_body",
    "services_image_alt",
    "big_picture_heading",
    "big_picture_body",
    "big_picture_image_alt",
    "discover_more_label",
    "specs_eyebrow",
    "specs_heading",
    "how_to_heading",
    "events_eyebrow",
    "events_heading",
    "events_body",
    "events_cta_label",
    "band_heading",
    "band_body",
    "band_cta_label",
)


@register(HomePage)
class HomePageTranslation(TranslationOptions):
    fields = HOME_TRANSLATED_FIELDS


@register(HeroSlide)
class HeroSlideTranslation(TranslationOptions):
    fields = ("eyebrow", "title", "body", "cta_label")


@register(HomeStat)
class HomeStatTranslation(TranslationOptions):
    fields = ("label",)


@register(HomeSectionItem)
class HomeSectionItemTranslation(TranslationOptions):
    fields = ("title", "body")
