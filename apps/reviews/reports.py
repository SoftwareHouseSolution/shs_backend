"""The dashboard's Client reviews section (see apps.core.admin_utils.dashboard_callback)."""

from collections import Counter

from django.db.models import Count, Q
from django.urls import reverse
from django.utils.translation import gettext as _

from .models import Review

RATING_TONES = {Review.Rating.GOOD: "success", Review.Rating.OK: "primary", Review.Rating.LOW: "danger"}
STATUS_TONES = {Review.Status.NEW: "danger", Review.Status.PUBLISHED: "success", Review.Status.ARCHIVED: "neutral"}


def _pct(n: int, total: int) -> int:
    return round(100 * n / total) if total else 0


def _breakdown(field: str, total: int, changelist: str) -> list[dict]:
    counts = dict(Review.objects.values_list(field).annotate(n=Count("id")))
    return [
        {
            "label": rating.label,
            "count": counts.get(rating.value, 0),
            "pct": _pct(counts.get(rating.value, 0), total),
            "tone": RATING_TONES[rating],
            "link": f"{changelist}?{field}__exact={rating.value}",
        }
        for rating in Review.Rating
    ]


def dashboard_context() -> dict:
    changelist = reverse("admin:reviews_review_changelist")
    totals = Review.objects.aggregate(
        total=Count("id"),
        new=Count("id", filter=Q(status=Review.Status.NEW)),
        published=Count("id", filter=Q(status=Review.Status.PUBLISHED)),
        follow_up=Count("id", filter=Q(support=Review.Rating.LOW) | Q(updates=Review.Rating.LOW)),
        good_support=Count("id", filter=Q(support=Review.Rating.GOOD)),
    )
    total = totals["total"]

    benefits = Counter(code for codes in Review.objects.values_list("benefits", flat=True) for code in codes)
    labels = dict(Review.Benefit.choices)
    top = benefits.most_common()
    top_max = top[0][1] if top else 0

    return {
        "review_total": total,
        "review_kpis": [
            {"title": _("Reviews received"), "value": total, "icon": "reviews", "link": changelist},
            {"title": _("Waiting for you"), "value": totals["new"], "icon": "mark_email_unread",
             "link": f"{changelist}?status__exact={Review.Status.NEW.value}"},
            {"title": _("Published on the site"), "value": totals["published"], "icon": "public",
             "link": f"{changelist}?status__exact={Review.Status.PUBLISHED.value}"},
            {"title": _("Rate support excellent"), "value": f"{_pct(totals['good_support'], total)}%", "icon": "support_agent",
             "link": f"{changelist}?support__exact={Review.Rating.GOOD.value}"},
            {"title": _("Need follow-up"), "value": totals["follow_up"], "icon": "flag", "link": f"{changelist}?status__exact={Review.Status.NEW.value}"},
        ],
        "review_support": _breakdown("support", total, changelist),
        "review_updates": _breakdown("updates", total, changelist),
        "review_benefits": [
            {"label": labels.get(code, code), "count": n, "pct": _pct(n, total), "bar": _pct(n, top_max)} for code, n in top
        ],
        "latest_reviews": [
            {
                "review": r,
                "url": reverse("admin:reviews_review_change", args=[r.pk]),
                "tone": STATUS_TONES.get(r.status, "neutral"),
            }
            for r in Review.objects.order_by("-created_at")[:5]
        ],
    }
