from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter

from apps.core.pagination import LargeResultsPagination
from apps.core.schema import api_schema, envelope
from apps.core.views import CachedObjectView, EnvelopeListAPIView

from . import selectors
from .models import Client
from .serializers import ClientSerializer, RegionSerializer, TaxonomyItemSerializer, TaxonomySerializer


class ClientFilter(filters.FilterSet):
    region = filters.CharFilter(field_name="region__key")
    sector = filters.CharFilter(field_name="sector__key")
    business_type = filters.CharFilter(field_name="business_types__key", distinct=True)
    featured = filters.BooleanFilter(method="filter_featured", label="Featured on the Customers page")

    class Meta:
        model = Client
        fields = ["region", "sector", "business_type", "featured"]

    def filter_featured(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.filter(featured_order__isnull=not value)


class ClientListView(EnvelopeListAPIView):
    """The roster. Up to 500 per page, so the directory can load it whole in one request
    and filter client-side; the filters here serve every other consumer."""

    serializer_class = ClientSerializer
    pagination_class = LargeResultsPagination
    cache_namespace = "clients"
    filterset_class = ClientFilter
    search_fields = ["name", "location"]
    ordering_fields = ["name", "featured_order"]
    ordering = ["name"]

    def get_queryset(self):
        return selectors.published_clients()

    @api_schema(
        summary="Published clients",
        responses={200: ClientSerializer(many=True)},
        parameters=[
            OpenApiParameter("featured", bool, description="Only (or never) the Customers-page featured strip."),
        ],
        tags=["clients"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ClientTaxonomyView(CachedObjectView):
    """Regions (with published-client counts and map pins), sectors and business types."""

    cache_namespace = "client-taxonomy"

    @api_schema(summary="Client filters and map regions", responses={200: envelope(TaxonomySerializer)}, tags=["clients"])
    def get(self, request, **kwargs):
        return super().get(request, **kwargs)

    def build(self, request, **kwargs):
        regions = list(selectors.regions_with_counts())
        return {
            "regions": RegionSerializer(regions, many=True).data,
            "sectors": TaxonomyItemSerializer(selectors.sectors(), many=True).data,
            "business_types": TaxonomyItemSerializer(selectors.business_types(), many=True).data,
            "total_clients": sum(r.client_count for r in regions),
        }
