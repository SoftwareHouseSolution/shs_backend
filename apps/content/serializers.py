from rest_framework import serializers

from apps.core.serializers import MediaUrlField

from .models import Partner, Testimonial


class TestimonialSerializer(serializers.ModelSerializer):
    avatar = MediaUrlField()
    attribution = serializers.CharField(read_only=True)

    class Meta:
        model = Testimonial
        fields = ["id", "quote", "author_name", "author_company", "attribution", "avatar"]


class PartnerSerializer(serializers.ModelSerializer):
    logo = MediaUrlField()

    class Meta:
        model = Partner
        fields = ["id", "name", "logo", "website", "category"]


class ComparisonColumnSerializer(serializers.Serializer):
    label = serializers.CharField()
    highlight = serializers.BooleanField()


class ComparisonCellSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    text = serializers.CharField()


class ComparisonRowSerializer(serializers.Serializer):
    cells = ComparisonCellSerializer(many=True)


class ComparisonGridSerializer(serializers.Serializer):
    """Documents ComparisonTable.as_grid()."""

    columns = ComparisonColumnSerializer(many=True)
    rows = ComparisonRowSerializer(many=True)
