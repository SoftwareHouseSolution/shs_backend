from django.db.models import Prefetch, QuerySet

from .models import ComparisonCell, ComparisonRow, ComparisonTable, Partner, Testimonial


def comparison_table_queryset() -> QuerySet[ComparisonTable]:
    return ComparisonTable.objects.prefetch_related(
        "columns",
        Prefetch(
            "rows",
            queryset=ComparisonRow.objects.prefetch_related(
                Prefetch("cells", queryset=ComparisonCell.objects.select_related("column"))
            ),
        ),
    )


def published_testimonials() -> QuerySet[Testimonial]:
    return Testimonial.objects.published().order_by("order", "id")


def featured_testimonial() -> Testimonial | None:
    return published_testimonials().filter(is_featured=True).first() or published_testimonials().first()


def active_partners(category: str | None = None) -> QuerySet[Partner]:
    qs = Partner.objects.filter(is_active=True).order_by("order", "id")
    return qs.filter(category=category) if category else qs
