from apps.core.schema import ERROR_404, api_schema, envelope
from apps.core.views import EnvelopeListAPIView, EnvelopeRetrieveAPIView

from . import selectors
from .serializers import EventSerializer


class EventListView(EnvelopeListAPIView):
    serializer_class = EventSerializer
    cache_namespace = "events"
    search_fields = ["title_en", "title_ar", "body_en", "body_ar"]
    ordering_fields = ["order", "year"]

    def get_queryset(self):
        return selectors.published_events()

    @api_schema(summary="Published events, newest first", responses={200: EventSerializer(many=True)}, tags=["events"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class EventDetailView(EnvelopeRetrieveAPIView):
    serializer_class = EventSerializer
    cache_namespace = "event"
    lookup_field = "slug"

    def get_queryset(self):
        return selectors.published_events()

    @api_schema(summary="One event", responses={200: envelope(EventSerializer), 404: ERROR_404}, tags=["events"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
