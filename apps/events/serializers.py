from rest_framework import serializers

from apps.core.serializers import MediaUrlField

from .models import Event, EventPhoto


class PhotoSerializer(serializers.ModelSerializer):
    src = MediaUrlField(source="image")

    class Meta:
        model = EventPhoto
        fields = ["src", "alt"]


class EventSerializer(serializers.ModelSerializer):
    """The frontend's TimelineEntry: year (nullable), title, paragraphs, photos."""

    year = serializers.SerializerMethodField()
    paras = serializers.ListField(source="paragraphs", child=serializers.CharField(), read_only=True)
    photos = PhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = ["slug", "year", "title", "paras", "photos"]

    def get_year(self, obj) -> str | None:
        return obj.year or None


class EventSummarySerializer(serializers.ModelSerializer):
    """One card in the home page's events rail: first paragraph and first photo."""

    year = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ["slug", "year", "title", "summary", "photo"]

    def get_year(self, obj) -> str | None:
        return obj.year or None

    def get_summary(self, obj) -> str:
        paras = obj.paragraphs
        return paras[0] if paras else ""

    def get_photo(self, obj) -> dict | None:
        photo = next(iter(obj.photos.all()), None)
        return PhotoSerializer(photo, context=self.context).data if photo else None
