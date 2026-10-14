from rest_framework import serializers

from .services import MAX_VIEW_DURATION_MS


class ViewReportSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    visitor_id = serializers.UUIDField()
    view_id = serializers.UUIDField()
    path = serializers.RegexField(r"^/[^\s]*$", max_length=300)
    language = serializers.ChoiceField(choices=["en", "ar"], required=False, allow_blank=True, default="")
    referrer = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    duration_ms = serializers.IntegerField(min_value=0, max_value=24 * 60 * 60 * 1000, required=False, default=0)

    def validate_path(self, value: str) -> str:
        # Query strings and fragments can carry personal data (search terms, tokens).
        return value.split("?", 1)[0].split("#", 1)[0] or "/"

    def validate_duration_ms(self, value: int) -> int:
        return min(value, MAX_VIEW_DURATION_MS)
