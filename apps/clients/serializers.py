from rest_framework import serializers

from apps.core.serializers import MediaUrlField

from .models import Client, Region


class TaxonomyItemSerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()


class RegionSerializer(serializers.ModelSerializer):
    client_count = serializers.IntegerField(read_only=True)
    map_pin = serializers.SerializerMethodField()

    class Meta:
        model = Region
        fields = ["key", "name", "client_count", "map_pin"]

    def get_map_pin(self, obj) -> dict | None:
        if obj.map_latitude is None:
            return None
        return {"lat": float(obj.map_latitude), "lng": float(obj.map_longitude)}


class ClientSerializer(serializers.ModelSerializer):
    logo = MediaUrlField()
    region = serializers.SlugRelatedField(slug_field="key", read_only=True)
    sector = serializers.SlugRelatedField(slug_field="key", read_only=True)
    business_types = serializers.SlugRelatedField(slug_field="key", many=True, read_only=True)

    class Meta:
        model = Client
        fields = ["slug", "name", "location", "region", "sector", "business_types", "logo", "featured_order"]


class ClientLogoSerializer(serializers.ModelSerializer):
    """Just enough to draw a mark in a logo strip."""

    logo = MediaUrlField()

    class Meta:
        model = Client
        fields = ["slug", "name", "logo"]


class TaxonomySerializer(serializers.Serializer):
    regions = RegionSerializer(many=True)
    sectors = TaxonomyItemSerializer(many=True)
    business_types = TaxonomyItemSerializer(many=True)
    total_clients = serializers.IntegerField()

