from modeltranslation.translator import TranslationOptions, register

from .models import ComparisonCell, ComparisonColumn, Testimonial


@register(ComparisonColumn)
class ComparisonColumnTranslation(TranslationOptions):
    fields = ("label",)


@register(ComparisonCell)
class ComparisonCellTranslation(TranslationOptions):
    fields = ("text",)


@register(Testimonial)
class TestimonialTranslation(TranslationOptions):
    fields = ("quote", "author_name", "author_company")
