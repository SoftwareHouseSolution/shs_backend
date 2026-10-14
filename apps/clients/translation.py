from modeltranslation.translator import TranslationOptions, register

from .models import BusinessType, Region, Sector


@register(Region)
class RegionTranslation(TranslationOptions):
    fields = ("name",)


@register(Sector)
class SectorTranslation(TranslationOptions):
    fields = ("name",)


@register(BusinessType)
class BusinessTypeTranslation(TranslationOptions):
    fields = ("name",)
