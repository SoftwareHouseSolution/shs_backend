from modeltranslation.translator import TranslationOptions, register

from .models import Event, EventPhoto


@register(Event)
class EventTranslation(TranslationOptions):
    fields = ("title", "body")


@register(EventPhoto)
class EventPhotoTranslation(TranslationOptions):
    fields = ("alt",)
