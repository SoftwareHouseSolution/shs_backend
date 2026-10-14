from apps.core.schema import ERROR_404, api_schema, envelope
from apps.core.views import EnvelopeListAPIView, EnvelopeRetrieveAPIView

from . import selectors
from .serializers import PageDetailSerializer, PageSummarySerializer


class PageListView(EnvelopeListAPIView):
    """Published pages — the frontend builds its route list from this."""

    serializer_class = PageSummarySerializer
    cache_namespace = "pages"
    search_fields = ["title_en", "title_ar", "slug"]
    ordering_fields = ["order", "slug", "updated_at"]
    filterset_fields = ["template"]

    def get_queryset(self):
        return selectors.published_pages()

    @api_schema(summary="Published pages", responses={200: PageSummarySerializer(many=True)}, tags=["pages"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PageDetailView(EnvelopeRetrieveAPIView):
    serializer_class = PageDetailSerializer
    cache_namespace = "page"
    lookup_field = "slug"

    def get_queryset(self):
        return selectors.page_with_blocks()

    @api_schema(
        summary="One page with its content blocks",
        responses={200: envelope(PageDetailSerializer), 404: ERROR_404},
        tags=["pages"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
