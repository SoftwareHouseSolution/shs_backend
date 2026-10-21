"""Admin → Inbox → Client reviews. Reviews arrive from the website; editors read them,
follow up on low ratings, and publish the good ones as testimonials in one click."""

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from unfold.decorators import action, display

from apps.core.admin_utils import PlainAdmin, image_tag

from .models import Review
from .services import PublishRefused, publish


def new_review_badge(request):
    """Sidebar badge (settings.UNFOLD): reviews nobody has handled yet."""
    return Review.objects.filter(status=Review.Status.NEW).count() or None


def _as_written(text: str):
    """The client's text with its line breaks, in its own direction (Arabic right-aligned)."""
    return format_html('<div dir="auto" style="white-space: pre-line; line-height: 1.8">{}</div>', text)


RATING_TONES = {Review.Rating.GOOD.label: "success", Review.Rating.OK.label: "info", Review.Rating.LOW.label: "danger"}


@admin.register(Review)
class ReviewAdmin(PlainAdmin):
    list_display = ["shop_name", "author_name", "place", "support_label", "updates_label", "consent", "status_label", "created_at"]
    list_filter = ["status", "support", "updates", "duration", "consent", "governorate", "source", "created_at"]
    search_fields = ["author_name", "shop_name", "governorate", "area", "text", "comment"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "reference", "review_text", "own_words", "author_name", "shop_name", "governorate", "area", "photo_preview",
        "duration", "support", "updates", "benefit_list", "consent", "language", "source",
        "testimonial_link", "created_at", "updated_at",
    ]
    fieldsets = [
        (_("Review"), {"fields": ["reference", "review_text", "own_words"]}),
        (_("Client"), {"fields": ["author_name", "shop_name", "governorate", "area", "photo_preview"]}),
        (_("Answers"), {"fields": ["duration", "support", "updates", "benefit_list"]}),
        (_("Context"), {"fields": ["consent", "language", "source", "created_at", "updated_at"]}),
        (_("Follow-up"), {"fields": ["status", "testimonial_link", "internal_notes"]}),
    ]
    actions = ["publish_selected", "archive_selected"]
    actions_detail = ["publish_this"]

    def has_add_permission(self, request):
        return False

    # ── Columns and read-only fields ─────────────────────────────────────────────────

    @display(description=_("Place"))
    def place(self, obj):
        return obj.place

    @display(description=_("Support"), ordering="support", label=RATING_TONES)
    def support_label(self, obj):
        return obj.get_support_display()

    @display(description=_("Updates"), ordering="updates", label=RATING_TONES)
    def updates_label(self, obj):
        return obj.get_updates_display()

    @display(
        description=_("Status"),
        ordering="status",
        label={Review.Status.NEW.label: "info", Review.Status.PUBLISHED.label: "success", Review.Status.ARCHIVED.label: "warning"},
    )
    def status_label(self, obj):
        return obj.get_status_display()

    @display(description=_("Reference"))
    def reference(self, obj):
        return obj.reference

    @display(description=_("Review"))
    def review_text(self, obj):
        return _as_written(obj.text)

    @display(description=_("In their own words"))
    def own_words(self, obj):
        return _as_written(obj.comment) if obj.comment else "—"

    @display(description=_("Shop photo"))
    def photo_preview(self, obj):
        return image_tag(obj.photo, height=160)

    @display(description=_("Helped with"))
    def benefit_list(self, obj):
        return format_html_join(" ", '<span class="swh-pill">{}</span>', ((label,) for label in obj.benefit_labels())) or "—"

    @display(description=_("Testimonial"))
    def testimonial_link(self, obj):
        if not obj.testimonial_id:
            return "—"
        url = reverse("admin:content_testimonial_change", args=[obj.testimonial_id])
        return format_html('<a class="swh-link" href="{}">{}</a>', url, _("Open the published testimonial"))

    # ── Actions ──────────────────────────────────────────────────────────────────────

    @action(description=_("Publish as testimonial"), permissions=["change"])
    def publish_selected(self, request, queryset):
        published = refused = 0
        for review in queryset.select_related("testimonial"):
            try:
                publish(review)
                published += 1
            except PublishRefused:
                refused += 1
        if published:
            self.message_user(request, _("%(n)d review(s) published on the website.") % {"n": published}, messages.SUCCESS)
        if refused:
            self.message_user(
                request,
                _("%(n)d review(s) were not published: the client did not agree to publication.") % {"n": refused},
                messages.WARNING,
            )

    @action(description=_("Archive (keep private)"), permissions=["change"])
    def archive_selected(self, request, queryset):
        n = queryset.filter(status=Review.Status.NEW).update(status=Review.Status.ARCHIVED)
        self.message_user(request, _("%(n)d review(s) archived.") % {"n": n}, messages.SUCCESS)

    @action(description=_("Publish as testimonial"), url_path="publish", icon="publish", permissions=["change"])
    def publish_this(self, request, object_id):
        review = self.get_object(request, object_id)
        try:
            testimonial = publish(review)
        except PublishRefused:
            self.message_user(request, _("This review cannot be published: the client did not agree to publication."), messages.ERROR)
            return redirect(reverse("admin:reviews_review_change", args=[object_id]))
        self.message_user(request, _("Published. You can edit the testimonial's wording here."), messages.SUCCESS)
        return redirect(reverse("admin:content_testimonial_change", args=[testimonial.pk]))
