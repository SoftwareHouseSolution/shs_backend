"""Serializer fields shared across apps."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .media import absolute_media_url


@extend_schema_field({"type": "string", "format": "uri", "nullable": True})
class MediaUrlField(serializers.Field):
    """A stored file as an absolute, browser-loadable URL (or null when empty)."""

    def __init__(self, **kwargs):
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def to_representation(self, value):
        return absolute_media_url(value, self.context.get("request"))


def media_url(serializer: serializers.Serializer, file_field) -> str | None:
    return absolute_media_url(file_field, serializer.context.get("request"))
