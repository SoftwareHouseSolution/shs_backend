from django.db.models import Prefetch, QuerySet

from .models import BlockItem, Page, PageBlock


def published_pages() -> QuerySet[Page]:
    return Page.objects.published().order_by("order", "id")


def page_with_blocks() -> QuerySet[Page]:
    return published_pages().prefetch_related(
        Prefetch(
            "blocks",
            queryset=PageBlock.objects.filter(is_visible=True)
            .select_related("comparison_table", "event")
            .prefetch_related(Prefetch("items", queryset=BlockItem.objects.order_by("order", "id")), "event__photos")
            .order_by("order", "id"),
        )
    )
