"""Admin → Inbox → Client reviews. Reviews arrive from the website; editors read them,
follow up on low ratings, and decide which ones the website shows."""

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from unfold.decorators import action, display

from apps.core.admin_utils import PlainAdmin, image_tag

from .models import Review
from .services import publish, withdraw


def new_review_badge(request):
    """Sidebar badge (settings.UNFOLD): reviews nobody has handled yet."""
    return Review.objects.filter(status=Review.Status.NEW).count() or None


def _as_written(text: str):
    """The client's text with its line breaks, in its own direction (Arabic right-aligned)."""
    return format_html('<div dir="auto" style="white-space: pre-line; line-height: 1.8">{}</div>', text)


RATING_TONES = {Review.Rating.GOOD.label: "success", Review.Rating.OK.label: "info", Review.Rating.LOW.label: "danger"}


@admin.register(Review)
class ReviewAdmin(PlainAdmin):
    """The buttons at the top of a review decide what the website shows: "Publish as
    testimonial" puts it on the Testimonials page, "Remove from website" takes it off.
    The status follows those buttons and cannot be edited by hand, so the label and the
    website never disagree."""

    list_display = ["shop_name", "author_name", "place", "support_label", "updates_label", "status_label", "created_at"]
    list_filter = ["status", "support", "updates", "duration", "governorate", "source", "created_at"]
    search_fields = ["author_name", "shop_name", "governorate", "area", "text", "comment"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "reference", "review_text", "own_words", "author_name", "shop_name", "governorate", "area", "photo_preview",
        "duration", "support", "updates", "benefit_list", "language", "source",
        "status_label", "testimonial_link", "created_at", "updated_at",
    ]
    fieldsets = [
        (_("Review"), {"fields": ["reference", "review_text", "own_words"]}),
        # The photo is the one thing an editor may change (a better shot, or none at all);
        # everything else is the client's own submission and stays read-only.
        (_("Client"), {"fields": ["author_name", "shop_name", "governorate", "area", ("photo", "photo_preview")]}),
        (_("Answers"), {"fields": ["duration", "support", "updates", "benefit_list"]}),
        (_("Context"), {"fields": ["language", "source", "created_at", "updated_at"]}),
        (_("Follow-up"), {"fields": ["status_label", "testimonial_link", "internal_notes"]}),
    ]
    actions = ["publish_selected", "withdraw_selected", "archive_selected"]
    actions_detail = ["publish_this", "withdraw_this"]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        """A new photo also replaces the one on the review's testimonial — unless an editor
        already gave the testimonial a different photo of its own, which is kept."""
        super().save_model(request, obj, form, change)
        if "photo" not in form.changed_data or not obj.testimonial_id:
            return
        previous = form.initial.get("photo")
        testimonial = obj.testimonial
        if testimonial.avatar.name in ("", getattr(previous, "name", previous) or ""):
            testimonial.avatar = obj.photo.name if obj.photo else ""
            testimonial.save(update_fields=["avatar", "updated_at"])
            if testimonial.is_published:
                self.message_user(request, _("The new photo is on the website too."), messages.SUCCESS)

    # One of the two buttons at the top, depending on whether the review is on the site.

    def _is_live(self, object_id) -> bool:
        return Review.objects.filter(pk=object_id, status=Review.Status.PUBLISHED).exists()

    def has_publish_review_permission(self, request, object_id=None):
        return self.has_change_permission(request) and (object_id is None or not self._is_live(object_id))

    def has_withdraw_review_permission(self, request, object_id=None):
        return self.has_change_permission(request) and (object_id is None or self._is_live(object_id))

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
        label = _("On the website — edit its wording") if obj.status == Review.Status.PUBLISHED else _("Hidden from the website")
        return format_html('<a class="swh-link" href="{}">{}</a>', url, label)

    # ── Actions ──────────────────────────────────────────────────────────────────────

    @action(description=_("Publish as testimonial"), permissions=["change"])
    def publish_selected(self, request, queryset):
        for review in queryset.select_related("testimonial"):
            publish(review)
        self.message_user(request, _("%(n)d review(s) published on the website.") % {"n": queryset.count()}, messages.SUCCESS)

    @action(description=_("Remove from website"), permissions=["change"])
    def withdraw_selected(self, request, queryset):
        n = sum(withdraw(review) for review in queryset.select_related("testimonial"))
        self.message_user(request, _("%(n)d review(s) removed from the website.") % {"n": n}, messages.SUCCESS)

    @action(description=_("Archive (keep private)"), permissions=["change"])
    def archive_selected(self, request, queryset):
        n = queryset.filter(status=Review.Status.NEW).update(status=Review.Status.ARCHIVED)
        self.message_user(request, _("%(n)d review(s) archived.") % {"n": n}, messages.SUCCESS)

    @action(description=_("Publish as testimonial"), url_path="publish", icon="publish", permissions=["publish_review"])
    def publish_this(self, request, object_id):
        publish(self.get_object(request, object_id))
        self.message_user(request, _("The review is now on the website."), messages.SUCCESS)
        return redirect(reverse("admin:reviews_review_change", args=[object_id]))

    @action(description=_("Remove from website"), url_path="withdraw", icon="visibility_off", permissions=["withdraw_review"])
    def withdraw_this(self, request, object_id):
        withdraw(self.get_object(request, object_id))
        self.message_user(request, _("The review was taken off the website."), messages.WARNING)
        return redirect(reverse("admin:reviews_review_change", args=[object_id]))
