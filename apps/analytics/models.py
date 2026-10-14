"""Anonymous visit analytics: which pages a visit went through, in order, and how long each
was actually on screen.

Privacy by construction: a visitor is a random id generated in their browser, a session is
a random id per browser tab, and no IP address, cookie or personal data is stored. The
browser does not report at all when it sends Do-Not-Track or Global Privacy Control.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class VisitSession(models.Model):
    """One visit: a browser tab's journey through the site."""

    class Device(models.TextChoices):
        DESKTOP = "desktop", _("Desktop")
        TABLET = "tablet", _("Tablet")
        MOBILE = "mobile", _("Mobile")

    session_id = models.UUIDField(_("session"), unique=True)
    visitor_id = models.UUIDField(_("visitor"), db_index=True, help_text=_("Same for every visit from one browser."))
    started_at = models.DateTimeField(_("started"), db_index=True)
    last_seen_at = models.DateTimeField(_("last activity"))
    language = models.CharField(_("language"), max_length=5, blank=True)
    landing_path = models.CharField(_("landing page"), max_length=300)
    referrer_host = models.CharField(_("came from"), max_length=255, blank=True)
    device = models.CharField(_("device"), max_length=10, choices=Device.choices, default=Device.DESKTOP)
    browser = models.CharField(_("browser"), max_length=40, blank=True)
    os = models.CharField(_("operating system"), max_length=40, blank=True)

    class Meta:
        verbose_name = _("visit")
        verbose_name_plural = _("visits")
        ordering = ["-started_at"]

    def __str__(self):
        return f"{timezone.localtime(self.started_at):%Y-%m-%d %H:%M} · {str(self.visitor_id)[:8]}"


class PageView(models.Model):
    """One page within a visit. `duration_ms` is time the page was visible — a tab left in
    the background does not count."""

    view_id = models.UUIDField(_("view"), unique=True)
    session = models.ForeignKey(VisitSession, on_delete=models.CASCADE, related_name="views", verbose_name=_("visit"))
    sequence = models.PositiveIntegerField(_("step"))
    path = models.CharField(_("page"), max_length=300, db_index=True)
    entered_at = models.DateTimeField(_("opened at"), db_index=True)
    duration_ms = models.PositiveIntegerField(_("time on page (ms)"), default=0)

    class Meta:
        verbose_name = _("page view")
        verbose_name_plural = _("page views")
        ordering = ["session_id", "sequence"]
        indexes = [models.Index(fields=["session", "sequence"], name="pageview_session_seq")]

    def __str__(self):
        return f"{self.path} ({self.duration_ms // 1000}s)"
