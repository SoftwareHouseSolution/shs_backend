from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.core.validators import image_validators

from .models import Review


class ReviewCreateSerializer(serializers.Serializer):
    """Sent as multipart/form-data so the shop photo can come along. `benefits` repeats
    (benefits=inventory&benefits=invoices)."""

    author_name = serializers.CharField(min_length=2, max_length=120)
    shop_name = serializers.CharField(min_length=2, max_length=160)
    governorate = serializers.CharField(max_length=80)
    area = serializers.CharField(max_length=120)
    photo = serializers.ImageField(required=False, allow_null=True, validators=image_validators)
    duration = serializers.ChoiceField(choices=Review.Duration.choices)
    support = serializers.ChoiceField(choices=Review.Rating.choices)
    updates = serializers.ChoiceField(choices=Review.Rating.choices)
    benefits = serializers.ListField(
        child=serializers.ChoiceField(choices=Review.Benefit.choices), min_length=1, max_length=len(Review.Benefit)
    )
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    text = serializers.CharField(min_length=20, max_length=4000)
    consent = serializers.BooleanField(default=False)
    source = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    # Honeypot: hidden in the form, so only bots fill it in.
    website = serializers.CharField(required=False, allow_blank=True, default="", write_only=True)

    def validate_benefits(self, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(value))
        if len(unique) != len(value):
            raise serializers.ValidationError(_("Each benefit can be chosen once."))
        return unique

    def validate_source(self, value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum() or ch in "-_")[:60]

    @property
    def is_bot(self) -> bool:
        return bool(self.validated_data.get("website"))


class ReviewReceiptSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)

    class Meta:
        model = Review
        fields = ["reference", "created_at"]
