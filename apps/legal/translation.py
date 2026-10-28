from modeltranslation.translator import TranslationOptions, register

from .models import LegalDocument


@register(LegalDocument)
class LegalDocumentTranslation(TranslationOptions):
    fields = ("title", "body")
