"""Read queries for site-wide content. Kept out of views and serializers so the same
queries serve the API, the admin dashboard and the tests."""

from django.db.models import Prefetch, QuerySet

from .models import Badge, FooterColumn, NavigationItem, SiteSettings, SocialLink


def get_site_settings() -> SiteSettings:
    return SiteSettings.load()


def active_children() -> Prefetch:
    return Prefetch(
        "children",
        queryset=NavigationItem.objects.filter(is_active=True).order_by("order", "id"),
        to_attr="active_children",
    )


def navigation_tree() -> QuerySet[NavigationItem]:
    """Active top-level items with their active children. Groups left with no active
    children are dropped — an empty dropdown is a dead end."""
    return (
        NavigationItem.objects.filter(parent__isnull=True, is_active=True)
        .prefetch_related(active_children())
        .order_by("order", "id")
    )


def footer_columns() -> QuerySet[FooterColumn]:
    return (
        FooterColumn.objects.filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "groups",
                queryset=NavigationItem.objects.filter(is_active=True)
                .prefetch_related(active_children())
                .order_by("order", "id"),
            )
        )
        .order_by("order", "id")
    )


def social_links() -> QuerySet[SocialLink]:
    return SocialLink.objects.filter(is_active=True).order_by("order", "id")


def badges() -> QuerySet[Badge]:
    return Badge.objects.filter(is_active=True).order_by("order", "id")


def parent_group_label_for(path: str) -> str | None:
    """The dropdown group a page sits under, for its breadcrumb ("About › Our Team")."""
    item = (
        NavigationItem.objects.filter(url=path, parent__isnull=False, is_active=True)
        .select_related("parent")
        .first()
    )
    return item.parent.label if item else None
