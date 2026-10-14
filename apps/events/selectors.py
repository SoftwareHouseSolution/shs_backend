from django.db.models import Prefetch, QuerySet

from .models import Event, EventPhoto


def published_events() -> QuerySet[Event]:
    return (
        Event.objects.published()
        .prefetch_related(Prefetch("photos", queryset=EventPhoto.objects.order_by("order", "id")))
        .order_by("order", "id")
    )
