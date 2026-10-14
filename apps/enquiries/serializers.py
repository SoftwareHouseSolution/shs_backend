import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Enquiry

_PHONE = re.compile(r"^\+?[0-9 ()\-]{6,30}$")


class EnquiryCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=120, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    company = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    message = serializers.CharField(min_length=10, max_length=5000, trim_whitespace=True)
    source_path = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    # Honeypot: hidden in the form, so only bots fill it in.
    website = serializers.CharField(required=False, allow_blank=True, default="", write_only=True)

    def validate_phone(self, value: str) -> str:
        if value and not _PHONE.match(value):
            raise serializers.ValidationError(_("Enter a valid phone number."))
        return value

    def validate_source_path(self, value: str) -> str:
        return value if value.startswith("/") else ""

    @property
    def is_bot(self) -> bool:
        return bool(self.validated_data.get("website"))


class EnquiryReceiptSerializer(serializers.ModelSerializer):
    reference = serializers.SerializerMethodField()

    class Meta:
        model = Enquiry
        fields = ["reference", "created_at"]

    def get_reference(self, obj) -> str:
        return f"ENQ-{obj.pk:06d}" if obj.pk else "ENQ-000000"
