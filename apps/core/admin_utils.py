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
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationAdmin, TranslationStackedInline, TranslationTabularInline
from modeltranslation.translator import NotRegistered, translator
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.decorators import action, display

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


class RtlArabicMixin:
    """Arabic inputs type and display right-to-left, in the admin as on the site."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and getattr(db_field, "language", None) == "ar":
            widget = getattr(field.widget, "widget", field.widget)
            widget.attrs.update({"dir": "rtl", "lang": "ar"})
        return field


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


class PlainAdmin(ModelAdmin):
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


def dashboard_callback(request, context):
    """Counts and gaps an editor wants on landing: what is live, what is hidden, which
    records still need Arabic, and how many enquiries are waiting."""
    from apps.clients.models import Client
    from apps.enquiries.models import Enquiry
    from apps.events.models import Event
    from apps.home.models import HeroSlide
    from apps.pages.models import Page, PageBlock

    pages = Page.objects.all()
    untranslated = [
        p for p in pages.prefetch_related("blocks") if missing_arabic(p) or any(missing_arabic(b) for b in p.blocks.all())
    ]
    by_status = dict(Enquiry.objects.values_list("status").annotate(n=Count("id")))
    context.update(
        {
            "kpis": [
                {"title": _("Published pages"), "value": pages.filter(is_published=True).count(), "link": reverse("admin:pages_page_changelist")},
                {"title": _("Hero slides"), "value": HeroSlide.objects.filter(is_published=True).count(), "link": reverse("admin:home_homepage_changelist")},
                {"title": _("Clients"), "value": Client.objects.filter(is_published=True).count(), "link": reverse("admin:clients_client_changelist")},
                {"title": _("Events"), "value": Event.objects.filter(is_published=True).count(), "link": reverse("admin:events_event_changelist")},
                {"title": _("New enquiries"), "value": by_status.get("new", 0), "link": reverse("admin:enquiries_enquiry_changelist") + "?status__exact=new"},
            ],
            "untranslated_pages": untranslated,
            "content_blocks": PageBlock.objects.count(),
            **_visitor_context(),
        }
    )
    return context


def _visitor_context() -> dict:
    """The dashboard's Visitors section: last 7 days, a 14-day chart, top pages and the
    most recent visits with the path each one took."""
    import json
    from datetime import timedelta

    from django.utils import timezone

    from apps.analytics import reports

    since = timezone.now() - timedelta(days=7)
    stats = reports.summary(since)
    labels, values = reports.daily_visits(14)
    titles = reports.page_titles()
    return {
        "visitor_kpis": [
            {"title": _("Visitors (7 days)"), "value": stats.visitors},
            {"title": _("Visits"), "value": stats.visits},
            {"title": _("Page views"), "value": stats.page_views},
            {"title": _("Avg. time on site"), "value": stats.avg_visit},
            {"title": _("Pages per visit"), "value": stats.pages_per_visit},
        ],
        "visits_chart": json.dumps(
            {
                "labels": labels,
                "datasets": [{"label": str(_("Visits")), "data": values, "backgroundColor": "var(--color-primary-500)"}],
            }
        ),
        "top_pages": reports.top_pages(since),
        "recent_visits": [
            {
                "visit": v,
                "steps": reports.flow(v, titles),
                "total": reports.format_duration(v.total_ms),
                "url": reverse("admin:analytics_visitsession_change", args=[v.pk]),
            }
            for v in reports.recent_visits(8)
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
