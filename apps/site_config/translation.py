from modeltranslation.translator import TranslationOptions, register

from .models import Badge, FooterColumn, NavigationItem, SiteSettings


@register(SiteSettings)
class SiteSettingsTranslation(TranslationOptions):
    fields = (
        "site_name",
        "address",
        "primary_cta_label",
        "footer_blurb",
        "rights_text",
        "contact_heading",
        "contact_body",
        "contact_cta_label",
        "default_meta_title",
        "default_meta_description",
    )


@register(NavigationItem)
class NavigationItemTranslation(TranslationOptions):
    fields = ("label",)


@register(FooterColumn)
class FooterColumnTranslation(TranslationOptions):
    fields = ("title",)


@register(Badge)
class BadgeTranslation(TranslationOptions):
    fields = ("alt",)
