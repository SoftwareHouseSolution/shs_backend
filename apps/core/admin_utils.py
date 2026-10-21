"""Admin building blocks shared by every content admin.

`ContentAdmin` = Unfold's ModelAdmin + modeltranslation's TranslationAdmin, plus:
  - `translated_fieldsets()` — shared fields first, then one tab per language;
  - Arabic inputs rendered right-to-left;
  - a "translation" column flagging records whose Arabic is incomplete;
  - publish / unpublish bulk actions;
  - image previews.
"""

from django.conf import settings
from django.contrib import admin, messages
from django.db import models
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationAdmin, TranslationStackedInline, TranslationTabularInline
from modeltranslation.translator import NotRegistered, translator
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.decorators import action, display

from .media import LinkField

LANGUAGE_TABS = (("en", _("English")), ("ar", _("Arabic — العربية")))


def translated_fieldsets(
    *,
    translated: list[str],
    shared: list[str] | None = None,
    shared_title=None,
    extra: list[tuple] | None = None,
) -> list[tuple]:
    """Fieldsets with the language-neutral fields first and each language in its own tab.

    Unfold renders fieldsets that carry the "tab" class as tabs, so an editor works through
    one language at a time instead of scanning interleaved `title [en]` / `title [ar]` rows.
    """
    sets: list[tuple] = []
    if shared:
        sets.append((shared_title, {"fields": shared}))
    for code, label in LANGUAGE_TABS:
        sets.append((label, {"classes": ["tab"], "fields": [f"{name}_{code}" for name in translated]}))
    sets.extend(extra or [])
    return sets


def _translated_field_names(model) -> list[str]:
    try:
        fields = translator.get_options_for_model(model).fields
        return list(fields.keys() if isinstance(fields, dict) else fields)
    except NotRegistered:
        return []


def missing_arabic(obj) -> list[str]:
    """Translated fields that have English content but no Arabic."""
    gaps = []
    for name in _translated_field_names(type(obj)):
        if getattr(obj, f"{name}_en", None) and not getattr(obj, f"{name}_ar", None):
            gaps.append(name)
    return gaps


class DirectionalInputsMixin:
    """Every input types in the direction of what goes into it, whatever the admin's own
    language: Arabic copy right-to-left; English copy, links, addresses and slugs
    left-to-right — so an English field stays readable in the Arabic admin and vice versa."""

    LTR_FIELD_TYPES = (models.URLField, models.EmailField, models.SlugField)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is None:
            return field
        widget = getattr(field.widget, "widget", field.widget)
        language = getattr(db_field, "language", None)
        if language == "ar":
            widget.attrs.update({"dir": "rtl", "lang": "ar"})
        elif language == "en":
            widget.attrs.update({"dir": "ltr", "lang": "en"})
        elif isinstance(db_field, (*self.LTR_FIELD_TYPES, LinkField)) or db_field.name.startswith("phone"):
            widget.attrs.setdefault("dir", "ltr")
        return field


RtlArabicMixin = DirectionalInputsMixin  # earlier name, kept for imports


class TranslationStatusMixin:
    @display(description=_("Translation"), label={_("Complete"): "success", _("Arabic missing"): "warning"})
    def translation_status(self, obj):
        return _("Arabic missing") if missing_arabic(obj) else _("Complete")


class PublishActionsMixin:
    actions = ["publish_selected", "unpublish_selected"]

    @action(description=_("Publish selected"))
    def publish_selected(self, request, queryset):
        updated = queryset.update(is_published=True)
        self._signal_bulk_change(queryset)
        self.message_user(request, _("%(n)d item(s) published.") % {"n": updated}, messages.SUCCESS)

    @action(description=_("Unpublish selected"))
    def unpublish_selected(self, request, queryset):
        updated = queryset.update(is_published=False)
        self._signal_bulk_change(queryset)
        self.message_user(request, _("%(n)d item(s) unpublished.") % {"n": updated}, messages.SUCCESS)

    @staticmethod
    def _signal_bulk_change(queryset):
        # QuerySet.update() sends no post_save, so tell the content cache directly.
        from .cache import bump_content_version

        bump_content_version()


class ContentAdmin(RtlArabicMixin, TranslationStatusMixin, ModelAdmin, TranslationAdmin):
    """Base admin for translated content models."""

    list_per_page = 50
    warn_unsaved_form = True
    compressed_fields = True


class PlainAdmin(DirectionalInputsMixin, ModelAdmin):
    """Base admin for models with nothing to translate."""

    list_per_page = 50
    warn_unsaved_form = True
    compressed_fields = True


class TranslatedTabularInline(RtlArabicMixin, TabularInline, TranslationTabularInline):
    extra = 0


class TranslatedStackedInline(RtlArabicMixin, StackedInline, TranslationStackedInline):
    extra = 0


class SingletonAdminMixin:
    """For SingletonModel subclasses: the list view jumps straight to the one record, and
    it can be neither added twice nor deleted."""

    def has_add_permission(self, request):
        return not self.model.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.objects.first()
        opts = self.model._meta
        if obj is None:
            return HttpResponseRedirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_add"))
        return HttpResponseRedirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk]))


def image_tag(file_field, *, height: int = 64, rounded: bool = True):
    if not file_field:
        return "—"
    return format_html(
        '<img src="{}" alt="" style="height:{}px;max-width:220px;object-fit:contain;{}" loading="lazy">',
        file_field.url,
        height,
        "border-radius:6px;" if rounded else "",
    )


def video_tag(file_field):
    if not file_field:
        return "—"
    return format_html(
        '<video src="{}" style="height:120px;border-radius:6px" muted controls preload="metadata"></video>',
        file_field.url,
    )


# ── Unfold callbacks (see settings.UNFOLD) ───────────────────────────────────────────


def environment_callback(request):
    if settings.DEBUG:
        return [_("Development"), "warning"]
    return [_("Production"), "success"]


def _greeting() -> str:
    from django.utils import timezone

    hour = timezone.localtime().hour
    if hour < 12:
        return _("Good morning")
    if hour < 18:
        return _("Good afternoon")
    return _("Good evening")


def _content_kpi(model, *, title, icon, link) -> dict:
    """A content card: how many records are live, and how many are hidden as drafts."""
    counts = model.objects.aggregate(total=Count("id"), live=Count("id", filter=models.Q(is_published=True)))
    hidden = counts["total"] - counts["live"]
    return {
        "title": title,
        "icon": icon,
        "value": counts["live"],
        "note": _("%(n)d hidden") % {"n": hidden} if hidden else _("All published"),
        "link": link,
    }


def dashboard_callback(request, context):
    """Counts and gaps an editor wants on landing: what is live, what is hidden, which
    records still need Arabic, and how many enquiries are waiting."""
    from apps.clients.models import Client
    from apps.enquiries.models import Enquiry
    from apps.events.models import Event
    from apps.home.models import HeroSlide
    from apps.pages.models import Page, PageBlock

    pages = list(Page.objects.prefetch_related("blocks"))
    untranslated = [p for p in pages if missing_arabic(p) or any(missing_arabic(b) for b in p.blocks.all())]
    translated_pct = round(100 * (len(pages) - len(untranslated)) / len(pages)) if pages else 100

    enquiries_url = reverse("admin:enquiries_enquiry_changelist")
    by_status = dict(Enquiry.objects.values_list("status").annotate(n=Count("id")))
    enquiry_total = sum(by_status.values())
    tones = {Enquiry.Status.NEW: "danger", Enquiry.Status.IN_PROGRESS: "warning", Enquiry.Status.CLOSED: "success"}
    pipeline = [
        {
            "label": status.label,
            "count": by_status.get(status.value, 0),
            "pct": round(100 * by_status.get(status.value, 0) / enquiry_total) if enquiry_total else 0,
            "tone": tones[status],
            "link": f"{enquiries_url}?status__exact={status.value}",
        }
        for status in Enquiry.Status
    ]
    user = request.user
    context.update(
        {
            "greeting": _greeting(),
            "display_name": user.get_short_name() or user.get_username(),
            "quick_actions": [
                {"title": _("New page"), "icon": "add", "link": reverse("admin:pages_page_add"), "primary": True},
                {"title": _("Enquiries"), "icon": "inbox", "link": enquiries_url},
                {"title": _("Site settings"), "icon": "tune", "link": reverse("admin:site_config_sitesettings_changelist")},
                {"title": _("View website"), "icon": "open_in_new", "link": settings.FRONTEND_URL, "external": True},
            ],
            "kpis": [
                {**_content_kpi(Page, title=_("Published pages"), icon="description", link=reverse("admin:pages_page_changelist")),
                 "tone": "primary"},
                {**_content_kpi(HeroSlide, title=_("Hero slides"), icon="view_carousel", link=reverse("admin:home_homepage_changelist")),
                 "tone": "violet"},
                {**_content_kpi(Client, title=_("Clients"), icon="storefront", link=reverse("admin:clients_client_changelist")),
                 "tone": "teal"},
                {**_content_kpi(Event, title=_("Events"), icon="event", link=reverse("admin:events_event_changelist")),
                 "tone": "amber"},
                {
                    "title": _("New enquiries"),
                    "icon": "mark_email_unread",
                    "value": by_status.get(Enquiry.Status.NEW, 0),
                    "note": _("Waiting for a reply") if by_status.get(Enquiry.Status.NEW) else _("Inbox is clear"),
                    "link": f"{enquiries_url}?status__exact={Enquiry.Status.NEW.value}",
                    "tone": "danger" if by_status.get(Enquiry.Status.NEW) else "success",
                },
            ],
            "pipeline": pipeline,
            "enquiry_total": enquiry_total,
            "latest_enquiries": [
                {"enquiry": e, "url": reverse("admin:enquiries_enquiry_change", args=[e.pk]), "tone": tones.get(e.status, "neutral")}
                for e in Enquiry.objects.order_by("-created_at")[:5]
            ],
            "untranslated_pages": untranslated,
            "page_count": len(pages),
            "translated_pct": translated_pct,
            "content_blocks": PageBlock.objects.count(),
            **_visitor_context(),
            **_review_context(),
        }
    )
    return context

def _review_context() -> dict:
    from apps.reviews.reports import dashboard_context

    return dashboard_context()


# A long visit's path is cut here on the dashboard; the visit's own page shows all of it.
RECENT_VISIT_STEPS = 8


def _visitor_context() -> dict:
    """The dashboard's Visitors section: last 7 days, a 14-day chart, top pages and the
    most recent visits with the path each one took."""
    import json
    from datetime import timedelta

    from django.utils import timezone

    from apps.analytics import reports
    from apps.analytics.models import VisitSession

    since = timezone.now() - timedelta(days=7)
    stats = reports.summary(since)
    labels, values = reports.daily_visits(14)
    titles = reports.page_titles()
    top = reports.top_pages(since)
    top_max = max((p.views for p in top), default=0)

    def shares(counts: dict[str, int], labels: dict[str, str], icons: dict[str, str]) -> list[dict]:
        total = sum(counts.values())
        return [
            {"label": labels.get(key, key), "icon": icons.get(key, ""), "count": n, "pct": round(100 * n / total) if total else 0}
            for key, n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

    device_icons = {"desktop": "computer", "tablet": "tablet_mac", "mobile": "smartphone"}
    return {
        "visitor_kpis": [
            {"title": _("Visitors (7 days)"), "value": stats.visitors, "icon": "group"},
            {"title": _("Visits"), "value": stats.visits, "icon": "login"},
            {"title": _("Page views"), "value": stats.page_views, "icon": "visibility"},
            {"title": _("Avg. time on site"), "value": stats.avg_visit, "icon": "schedule"},
            {"title": _("Pages per visit"), "value": stats.pages_per_visit, "icon": "layers"},
        ],
        "visits_chart": json.dumps(
            {
                "labels": labels,
                "datasets": [
                    {
                        "label": str(_("Visits")),
                        "data": values,
                        "backgroundColor": "var(--color-primary-500)",
                        "hoverBackgroundColor": "var(--color-primary-600)",
                        "borderRadius": 6,
                        "maxBarThickness": 28,
                    }
                ],
            }
        ),
        "top_pages": [{"page": p, "pct": round(100 * p.views / top_max) if top_max else 0} for p in top],
        "devices": shares(reports.devices(since), dict(VisitSession.Device.choices), device_icons),
        "languages": shares(
            reports.languages(since), {"en": _("English"), "ar": _("Arabic")}, {"en": "translate", "ar": "translate"}
        ),
        "recent_visits": [
            {
                "visit": v,
                "steps": steps[:RECENT_VISIT_STEPS],
                "more_steps": max(len(steps) - RECENT_VISIT_STEPS, 0),
                "total": reports.format_duration(v.total_ms),
                "device_icon": device_icons.get(v.device, "devices"),
                "url": reverse("admin:analytics_visitsession_change", args=[v.pk]),
            }
            for v in reports.recent_visits(6)
            for steps in [reports.flow(v, titles)]
        ],
    }



__all__ = [
    "ContentAdmin",
    "PlainAdmin",
    "TranslatedTabularInline",
    "TranslatedStackedInline",
    "SingletonAdminMixin",
    "PublishActionsMixin",
    "translated_fieldsets",
    "image_tag",
    "video_tag",
    "missing_arabic",
    "admin",
]
