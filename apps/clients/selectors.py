from django.db.models import Count, Q, QuerySet

from .models import BusinessType, Client, Region, Sector


def published_clients() -> QuerySet[Client]:
    return (
        Client.objects.published()
        .select_related("region", "sector")
        .prefetch_related("business_types")
        .order_by("name")
    )


def home_highlighted_clients() -> QuerySet[Client]:
    return published_clients().filter(home_highlight_order__isnull=False).order_by("home_highlight_order", "name")


def home_strip_clients() -> QuerySet[Client]:
    return published_clients().filter(show_in_home_strip=True)


def regions_with_counts() -> QuerySet[Region]:
    return Region.objects.annotate(
        client_count=Count("clients", filter=Q(clients__is_published=True))
    ).order_by("order", "id")


def sectors() -> QuerySet[Sector]:
    return Sector.objects.order_by("order", "id")


def business_types() -> QuerySet[BusinessType]:
    return BusinessType.objects.order_by("order", "id")
