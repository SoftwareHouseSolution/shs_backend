from django.utils.translation import get_language
from rest_framework import serializers

from apps.core.i18n import direction
from apps.core.serializers import MediaUrlField

from .models import Badge, NavigationItem, SiteSettings, SocialLink


class LinkSerializer(serializers.Serializer):
    label = serializers.CharField()
    url = serializers.CharField()


class SiteSettingsSerializer(serializers.ModelSerializer):
    logo_on_light = MediaUrlField()
    logo_on_dark = MediaUrlField()
    favicon = MediaUrlField()
    og_image = MediaUrlField()
    primary_cta = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()

    class Meta:
        model = SiteSettings
        fields = [
            "site_name",
            "short_name",
            "since_year",
            "logo_on_light",
            "logo_on_dark",
            "favicon",
            "og_image",
            "phone_display",
            "phone_link",
            "whatsapp_url",
            "sales_email",
            "careers_email",
            "address",
            "primary_cta",
            "contact",
            "footer_blurb",
            "copyright_year",
            "rights_text",
            "default_meta_title",
            "default_meta_description",
        ]

    def get_contact(self, obj) -> dict:
        return {"heading": obj.contact_heading, "body": obj.contact_body, "cta_label": obj.contact_cta_label}

    def get_primary_cta(self, obj) -> dict:
        return {"label": obj.primary_cta_label, "url": obj.primary_cta_url}


class NavLeafSerializer(serializers.ModelSerializer):
    class Meta:
        model = NavigationItem
        fields = ["key", "label", "url"]


class NavEntrySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = NavigationItem
        fields = ["key", "label", "url", "children"]

    def get_children(self, obj) -> list[dict]:
        children = getattr(obj, "active_children", None)
        if children is None:
            children = obj.children.filter(is_active=True)
        return NavLeafSerializer(children, many=True).data


class FooterColumnSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    links = serializers.SerializerMethodField()

    def get_links(self, obj) -> list[dict]:
        links = []
        for group in obj.groups.all():
            for child in getattr(group, "active_children", []):
                links.append({"label": child.label, "url": child.url})
        return links


class SocialLinkSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_platform_display")

    class Meta:
        model = SocialLink
        fields = ["platform", "label", "url", "is_placeholder"]


class BadgeSerializer(serializers.ModelSerializer):
    src = MediaUrlField(source="image")
    href = serializers.CharField(source="url")

    class Meta:
        model = Badge
        fields = ["src", "alt", "href"]


class LanguageSerializer(serializers.Serializer):
    code = serializers.CharField()
    dir = serializers.CharField()

    @staticmethod
    def current() -> dict:
        code = get_language()
        return {"code": code, "dir": direction(code)}


class SitePayloadSerializer(serializers.Serializer):
    """Documents the composed GET /site/ payload."""

    language = LanguageSerializer()
    settings = SiteSettingsSerializer()
    navigation = NavEntrySerializer(many=True)
    footer_columns = FooterColumnSerializer(many=True)
    social_links = SocialLinkSerializer(many=True)
    badges = BadgeSerializer(many=True)
