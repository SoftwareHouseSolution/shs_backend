from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.decorators import action, display

from apps.core.admin_utils import PlainAdmin

from .models import Enquiry


def new_enquiry_badge(request):
    """Sidebar badge (settings.UNFOLD) — the number of unread enquiries."""
    count = Enquiry.objects.filter(status=Enquiry.Status.NEW).count()
    return count or None


@admin.register(Enquiry)
class EnquiryAdmin(PlainAdmin):
    list_display = ["full_name", "email", "company", "language", "status_label", "created_at"]
    list_filter = ["status", "language", "created_at"]
    search_fields = ["full_name", "email", "company", "message"]
    date_hierarchy = "created_at"
    readonly_fields = ["full_name", "email", "phone", "company", "message", "language", "source_path", "created_at", "updated_at"]
    fieldsets = [
        (_("Message"), {"fields": ["full_name", "email", "phone", "company", "message"]}),
        (_("Context"), {"fields": ["language", "source_path", "created_at", "updated_at"]}),
        (_("Follow-up"), {"fields": ["status", "internal_notes"]}),
    ]
    actions = ["mark_in_progress", "mark_closed"]

    def has_add_permission(self, request):
        return False

    @display(
        description=_("Status"),
        ordering="status",
        label={Enquiry.Status.NEW.label: "info", Enquiry.Status.IN_PROGRESS.label: "warning", Enquiry.Status.CLOSED.label: "success"},
    )
    def status_label(self, obj):
        return obj.get_status_display()

    @action(description=_("Mark as in progress"))
    def mark_in_progress(self, request, queryset):
        queryset.update(status=Enquiry.Status.IN_PROGRESS)

    @action(description=_("Mark as closed"))
    def mark_closed(self, request, queryset):
        queryset.update(status=Enquiry.Status.CLOSED)
