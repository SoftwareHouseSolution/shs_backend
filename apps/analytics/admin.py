"""Read-only views of visitor analytics. Records are written only by the site itself."""

from django.contrib import admin
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from unfold.decorators import display

from apps.core.admin_utils import PlainAdmin

from . import reports
from .models import PageView, VisitSession


class _ReadOnly:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


def _flow_html(session, titles, *, limit: int | None = None):
    steps = reports.flow(session, titles)
    shown = steps[:limit] if limit else steps
    chips = format_html_join(
        mark_safe('<span class="text-base-400"> → </span>'),
        '<span class="whitespace-nowrap" title="{}"><b>{}</b> <span class="text-base-500">{}</span></span>',
        ((s.path, s.label, s.duration) for s in shown),
    )
    more = format_html(' <span class="text-base-400">+{}</span>', len(steps) - len(shown)) if len(steps) > len(shown) else ""
    return format_html("{}{}", chips, more)


@admin.register(VisitSession)
class VisitSessionAdmin(_ReadOnly, PlainAdmin):
    list_display = ["started_at", "visitor", "device", "language", "pages", "time_on_site", "flow"]
    list_filter = ["device", "language", "browser", "os", "started_at"]
    search_fields = ["landing_path", "referrer_host", "views__path"]
    date_hierarchy = "started_at"
    list_per_page = 50
    fieldsets = [
        (_("Visit"), {"fields": ["started_at", "last_seen_at", "time_on_site", "pages", "full_flow"]}),
        (_("Path through the site"), {"fields": ["timeline"]}),
        (_("Visitor"), {"fields": ["visitor_id", "session_id", "returning", "language", "device", "browser", "os", "referrer_host", "landing_path"]}),
    ]
    readonly_fields = [
        "started_at", "last_seen_at", "time_on_site", "pages", "full_flow", "timeline", "visitor_id", "session_id",
        "returning", "language", "device", "browser", "os", "referrer_host", "landing_path",
    ]

    def get_queryset(self, request):
        self._titles = reports.page_titles()
        return reports.sessions_with_totals().prefetch_related("views")

    @display(description=_("Visitor"))
    def visitor(self, obj):
        return str(obj.visitor_id)[:8]

    @display(description=_("Pages"), ordering="page_count")
    def pages(self, obj):
        return obj.page_count

    @display(description=_("Time on site"), ordering="total_ms")
    def time_on_site(self, obj):
        return reports.format_duration(obj.total_ms)

    @display(description=_("Flow"))
    def flow(self, obj):
        return _flow_html(obj, self._titles, limit=6)

    @display(description=_("Flow"))
    def full_flow(self, obj):
        return _flow_html(obj, self._titles)

    @display(description=_("Steps"))
    def timeline(self, obj):
        rows = format_html_join(
            "",
            '<tr class="border-t border-base-200 dark:border-base-800">'
            '<td style="padding:8px 28px 8px 0">{}</td><td style="padding:8px 28px 8px 0" class="font-medium">{}</td>'
            '<td style="padding:8px 28px 8px 0" class="text-base-500">{}</td><td style="padding:8px 28px 8px 0">{}</td><td style="padding:8px 28px 8px 0">{}</td></tr>',
            (
                (n, step.label, step.path, date_format(timezone.localtime(view.entered_at), "H:i:s"), step.duration)
                for n, (step, view) in enumerate(
                    zip(reports.flow(obj, self._titles), sorted(obj.views.all(), key=lambda v: (v.sequence, v.entered_at)), strict=True),
                    start=1,
                )
            ),
        )
        head = format_html(
            '<thead><tr class="text-subtle"><th style="padding:0 28px 8px 0" class="text-start font-normal">#</th>'
            '<th style="padding:0 28px 8px 0" class="text-start font-normal">{}</th><th style="padding:0 28px 8px 0" class="text-start font-normal">{}</th>'
            '<th style="padding:0 28px 8px 0" class="text-start font-normal">{}</th><th style="padding:0 28px 8px 0" class="text-start font-normal">{}</th></tr></thead>',
            _("Page"), _("Address"), _("Opened at"), _("Time on page"),
        )
        return format_html('<table class="text-sm">{}<tbody>{}</tbody></table>', head, rows)

    @display(description=_("Returning visitor"), boolean=True)
    def returning(self, obj):
        return VisitSession.objects.filter(visitor_id=obj.visitor_id, started_at__lt=obj.started_at).exists()


@admin.register(PageView)
class PageViewAdmin(_ReadOnly, PlainAdmin):
    list_display = ["entered_at", "page", "path", "time_on_page", "visit_link", "sequence"]
    list_filter = ["entered_at", "session__language", "session__device"]
    search_fields = ["path"]
    date_hierarchy = "entered_at"
    list_select_related = ["session"]
    list_per_page = 100

    def get_queryset(self, request):
        self._titles = reports.page_titles()
        return super().get_queryset(request)

    @display(description=_("Page"))
    def page(self, obj):
        return reports.label_for(obj.path, self._titles)

    @display(description=_("Time on page"), ordering="duration_ms")
    def time_on_page(self, obj):
        return reports.format_duration(obj.duration_ms)

    @display(description=_("Visit"))
    def visit_link(self, obj):
        from django.urls import reverse

        url = reverse("admin:analytics_visitsession_change", args=[obj.session_id])
        return format_html('<a class="text-primary-600" href="{}">{}</a>', url, str(obj.session.visitor_id)[:8])
