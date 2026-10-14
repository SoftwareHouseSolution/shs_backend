from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.serializers import MediaUrlField, media_url
from apps.site_config.selectors import parent_group_label_for

from .blocks import RenderContext, registered_kinds, serialize_block
from .models import Page


class PageSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ["slug", "template", "title", "updated_at"]


class PageVideoSerializer(serializers.Serializer):
    desktop = serializers.URLField()
    mobile = serializers.URLField(allow_null=True)
    poster_desktop = serializers.URLField(allow_null=True)
    poster_mobile = serializers.URLField(allow_null=True)


class BlockSerializer(serializers.Serializer):
    """Documentation shape. `kind` decides which other keys are present."""

    kind = serializers.ChoiceField(choices=registered_kinds())


class PageDetailSerializer(serializers.ModelSerializer):
    header_image = MediaUrlField()
    meta_title = serializers.SerializerMethodField()
    breadcrumb_parent = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()
    blocks = serializers.SerializerMethodField()

    class Meta:
        model = Page
        fields = [
            "slug",
            "template",
            "title",
            "eyebrow",
            "lede",
            "header_image",
            "meta_title",
            "meta_description",
            "breadcrumb_parent",
            "video",
            "blocks",
        ]

    def get_meta_title(self, obj) -> str:
        return obj.meta_title or obj.title

    def get_breadcrumb_parent(self, obj) -> str | None:
        return parent_group_label_for(obj.path)

    @extend_schema_field(PageVideoSerializer(allow_null=True))
    def get_video(self, obj):
        if not obj.video_desktop:
            return None
        return {
            "desktop": media_url(self, obj.video_desktop),
            "mobile": media_url(self, obj.video_mobile),
            "poster_desktop": media_url(self, obj.video_poster_desktop),
            "poster_mobile": media_url(self, obj.video_poster_mobile),
        }

    @extend_schema_field(BlockSerializer(many=True))
    def get_blocks(self, obj):
        ctx = RenderContext(request=self.context.get("request"))
        return [serialize_block(block, ctx) for block in obj.blocks.all()]
