from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.decorators import display

from apps.core.admin_utils import (
    ContentAdmin,
    PublishActionsMixin,
    TranslatedTabularInline,
    image_tag,
    translated_fieldsets,
)

from .models import Event, EventPhoto


class EventPhotoInline(TranslatedTabularInline):
    model = EventPhoto
    fields = ["preview", "image", "alt", "order"]
    readonly_fields = ["preview"]
    ordering_field = "order"
    hide_ordering_field = True

    @display(description=_("Preview"))
    def preview(self, obj):
        return image_tag(obj.image, height=56)


@admin.register(Event)
class EventAdmin(PublishActionsMixin, ContentAdmin):
    list_display = ["cover", "title", "year", "photo_count", "is_published", "translation_status"]
    list_filter = ["is_published", "year"]
    search_fields = ["title_en", "title_ar", "slug"]
    ordering_field = "order"
    hide_ordering_field = True
    prepopulated_fields = {"slug": ["title_en"]}
    inlines = [EventPhotoInline]
    fieldsets = translated_fieldsets(shared=["slug", "year", "is_published"], translated=["title", "body"])

    @display(description=_("Cover"))
    def cover(self, obj):
        photo = obj.photos.first()
        return image_tag(photo.image if photo else None, height=40)

    @display(description=_("Photos"))
    def photo_count(self, obj):
        return obj.photos.count()
