from django.utils.translation import get_language
from rest_framework import serializers

from apps.clients.serializers import ClientLogoSerializer
from apps.content.serializers import ComparisonGridSerializer, TestimonialSerializer
from apps.core.serializers import media_url
from apps.events.serializers import EventSummarySerializer

from .models import HeroSlide, HomeSectionItem, HomeStat


class HeroSlideSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()

    class Meta:
        model = HeroSlide
        fields = ["id", "eyebrow", "title", "body", "cta_label", "cta_url", "image", "video"]

    def get_image(self, obj) -> str | None:
        # Language-specific artwork wins when the editor supplied one.
        chosen = obj.image_ar if get_language() == "ar" and obj.image_ar else obj.image
        return media_url(self, chosen)

    def get_video(self, obj) -> dict | None:
        if not obj.video_mp4:
            return None
        return {"webm": media_url(self, obj.video_webm), "mp4": media_url(self, obj.video_mp4)}


class HomeStatSerializer(serializers.ModelSerializer):
    value = serializers.IntegerField(allow_null=True)
    text = serializers.SerializerMethodField()

    class Meta:
        model = HomeStat
        fields = ["label", "value", "prefix", "suffix", "text"]

    def get_text(self, obj) -> str | None:
        return obj.text or None


class SectionItemSerializer(serializers.ModelSerializer):
    n = serializers.CharField(source="number")

    class Meta:
        model = HomeSectionItem
        fields = ["n", "title", "body"]


# ── Documentation of the composed payload (see apps.home.composer) ─────────────────


class _Cta(serializers.Serializer):
    label = serializers.CharField()
    url = serializers.CharField()


class _Figures(serializers.Serializer):
    eyebrow = serializers.CharField()
    aria_label = serializers.CharField()
    stats = HomeStatSerializer(many=True)


class _Proof(serializers.Serializer):
    lede = serializers.CharField()
    strip_aria_label = serializers.CharField()
    cta = _Cta()
    highlighted = ClientLogoSerializer(many=True)
    strip = ClientLogoSerializer(many=True)


class _ImageSection(serializers.Serializer):
    eyebrow = serializers.CharField(required=False)
    heading = serializers.CharField()
    body = serializers.CharField()
    image = serializers.URLField(allow_null=True)
    image_alt = serializers.CharField()
    items = SectionItemSerializer(many=True)


class _Specs(ComparisonGridSerializer):
    eyebrow = serializers.CharField()
    heading = serializers.CharField()


class _HowTo(serializers.Serializer):
    heading = serializers.CharField()
    cta = _Cta()
    items = SectionItemSerializer(many=True)


class _Events(serializers.Serializer):
    eyebrow = serializers.CharField()
    heading = serializers.CharField()
    body = serializers.CharField()
    cta = _Cta()
    items = EventSummarySerializer(many=True)


class _Band(serializers.Serializer):
    heading = serializers.CharField()
    body = serializers.CharField()
    cta = _Cta()


class _Seo(serializers.Serializer):
    meta_title = serializers.CharField(allow_null=True)
    meta_description = serializers.CharField(allow_null=True)


class HomePayloadSerializer(serializers.Serializer):
    seo = _Seo()
    hero = HeroSlideSerializer(many=True)
    figures = _Figures()
    proof = _Proof()
    services = _ImageSection()
    big_picture = _ImageSection()
    discover_more_label = serializers.CharField()
    specs = _Specs(allow_null=True)
    testimonial = TestimonialSerializer(allow_null=True)
    how_to = _HowTo()
    events = _Events()
    band = _Band()
