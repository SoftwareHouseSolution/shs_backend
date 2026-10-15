"""Read-only views of visitor analytics. Records are written only by the site itself."""

from django.contrib import admin
from django.utils.html import format_html, format_html_join
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


def _flow_html(session, titles, *, limit: int):
    """The visit's path as chips, back-to-back repeats merged (Home ×3), cut after `limit`."""
    stops = reports.visit_report(session, titles).journey
    shown = stops[:limit]
    chips = format_html_join(
        format_html('<span class="swh-flow__arrow">{}</span>', reports.flow_arrow()),
        '<span class="swh-flow__step" title="{}">{}{} <small>{}</small></span>',
        ((s.path, s.label, f" ×{s.views}" if s.views > 1 else "", s.duration) for s in shown),
    )
    more = format_html('<span class="swh-flow__more">+{}</span>', len(stops) - len(shown)) if len(stops) > len(shown) else ""
    return format_html('<span class="swh-flow">{}{}</span>', chips, more)


@admin.register(VisitSession)
class VisitSessionAdmin(_ReadOnly, PlainAdmin):
    list_display = ["started_at", "visitor", "device", "language", "pages", "time_on_site", "flow"]
    list_filter = ["device", "language", "browser", "os", "started_at"]
    search_fields = ["landing_path", "referrer_host", "views__path"]
    date_hierarchy = "started_at"
    list_per_page = 50
    # The visit's page is a report, not a form: see templates/admin/analytics/visitsession/.
    change_form_template = "admin/analytics/visitsession/change_form.html"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        visit = self.get_object(request, object_id)
        if visit is not None:
            other = (
                reports.sessions_with_totals()
                .filter(visitor_id=visit.visitor_id)
                .exclude(pk=visit.pk)
                .order_by("-started_at")
            )
            extra_context = {
                **(extra_context or {}),
                "visit": visit,
                "report": reports.visit_report(visit, self._titles),
                "returning": self.returning(visit),
                "other_visits": [
                    {"visit": v, "total": reports.format_duration(v.total_ms)} for v in other[:6]
                ],
                "other_visit_count": other.count(),
                "flow_arrow": reports.flow_arrow(),
            }
        return super().change_view(request, object_id, form_url, extra_context)

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
        return _flow_html(obj, self._titles, limit=5)

    @display(description=_("Returning visitor"), boolean=True)
    def returning(self, obj) -> bool:
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
