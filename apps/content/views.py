from django_filters import rest_framework as filters

from apps.core.schema import api_schema
from apps.core.views import EnvelopeListAPIView

from . import selectors
from .models import Partner
from .serializers import PartnerSerializer, TestimonialSerializer


class TestimonialListView(EnvelopeListAPIView):
    serializer_class = TestimonialSerializer
    cache_namespace = "testimonials"
    filter_backends: list = []

    def get_queryset(self):
        return selectors.published_testimonials()

    @api_schema(summary="Published testimonials", responses={200: TestimonialSerializer(many=True)}, tags=["content"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PartnerFilter(filters.FilterSet):
    category = filters.ChoiceFilter(choices=Partner.Category.choices)

    class Meta:
        model = Partner
        fields = ["category"]


class PartnerListView(EnvelopeListAPIView):
    serializer_class = PartnerSerializer
    cache_namespace = "partners"
    filterset_class = PartnerFilter
    search_fields = ["name"]
    ordering_fields = ["order", "name"]

    def get_queryset(self):
        return selectors.active_partners()

    @api_schema(summary="Active partners", responses={200: PartnerSerializer(many=True)}, tags=["content"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
