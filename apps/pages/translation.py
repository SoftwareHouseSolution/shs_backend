from modeltranslation.translator import TranslationOptions, register

from .models import BlockItem, Page, PageBlock


@register(Page)
class PageTranslation(TranslationOptions):
    fields = ("title", "eyebrow", "lede", "meta_title", "meta_description")


@register(PageBlock)
class PageBlockTranslation(TranslationOptions):
    fields = ("eyebrow", "heading", "body", "label")


@register(BlockItem)
class BlockItemTranslation(TranslationOptions):
    fields = ("title", "body")
