"""Admin pages that are not tied to a model."""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from . import media_cleanup, system_status


class SystemStatusView(TemplateView):
    """Admin → System → System status. Superusers only: it shows host and database
    details an editor has no need for. Wrapped in admin_view() in config/urls.py, so
    signed-out visitors are sent to the admin login."""

    template_name = "admin/system/status.html"
    title = _("System status")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        request.current_app = admin.site.name
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        report = system_status.build_report(use_cache="refresh" not in self.request.GET)
        return {
            **super().get_context_data(**kwargs),
            **admin.site.each_context(self.request),
            "title": self.title,
            "report": report,
            "ttl": system_status.REPORT_TTL,
            "cleanup_url": reverse("admin-media-cleanup"),
        }


class MediaCleanupView(TemplateView):
    """Admin → System status → Clean up unused files. GET previews what would be moved;
    every change is a POST (CSRF-protected) that redirects back here. Superusers only."""

    template_name = "admin/system/media_cleanup.html"
    title = _("Media clean-up")
    PREVIEW = 100

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        request.current_app = admin.site.name
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action, batch = request.POST.get("action"), request.POST.get("batch", "")
        try:
            if action == "clean":
                moved = media_cleanup.move_unused_to_trash(request.user.get_username())
                if moved:
                    messages.success(request, _("%(n)d unused file(s) (%(size)s) moved to the trash. Nothing was deleted; restore them below if anything is missing.")
                                     % {"n": moved.count, "size": system_status.human_bytes(moved.size)})
                else:
                    messages.info(request, _("There are no unused files to clean up."))
            elif action == "restore":
                restored, skipped = media_cleanup.restore(batch)
                messages.success(request, _("%(n)d file(s) restored.") % {"n": restored})
                if skipped:
                    messages.warning(request, _("%(n)d file(s) were left in the trash because a file with the same name exists again.") % {"n": skipped})
            elif action == "purge":
                deleted = media_cleanup.purge(batch)
                messages.success(request, _("%(n)d file(s) permanently deleted.") % {"n": deleted})
        except LookupError:
            messages.error(request, _("That trash batch no longer exists."))
        return redirect("admin-media-cleanup")

    def get_context_data(self, **kwargs):
        unused, waiting = media_cleanup.unused_files()
        return {
            **super().get_context_data(**kwargs),
            **admin.site.each_context(self.request),
            "title": self.title,
            "unused": unused[: self.PREVIEW],
            "unused_count": len(unused),
            "unused_size": system_status.human_bytes(sum(f.size for f in unused)),
            "more": max(len(unused) - self.PREVIEW, 0),
            "waiting_count": len(waiting),
            "waiting_size": system_status.human_bytes(sum(f.size for f in waiting)),
            "waiting_until": media_cleanup.ready_at(waiting),
            "batches": media_cleanup.trash_batches(),
            "grace_minutes": int(media_cleanup.GRACE.total_seconds() // 60),
            "status_url": reverse("admin-system-status"),
        }
