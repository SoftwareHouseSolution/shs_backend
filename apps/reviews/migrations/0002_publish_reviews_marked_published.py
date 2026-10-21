"""Repair reviews whose status was set to Published from the status list before saving did
anything: they show "Published" in the admin but have no testimonial, so nothing reached
the website. Each one with the client's consent gets its testimonial now, exactly as the
"Publish as testimonial" button would make it; one without consent goes back to New."""

from django.db import migrations
from django.db.models import F


def _place(review) -> str:
    if not review.area or review.area == review.governorate:
        return review.governorate
    sep = "، " if review.language == "ar" else ", "
    return f"{review.area}{sep}{review.governorate}"


def publish_marked_reviews(apps, schema_editor):
    Review = apps.get_model("reviews", "Review")
    Testimonial = apps.get_model("content", "Testimonial")
    for review in Review.objects.filter(status="published", testimonial__isnull=True).order_by("created_at"):
        if not review.consent:
            review.status = "new"
            review.save(update_fields=["status"])
            continue
        lang = review.language if review.language in ("en", "ar") else "ar"
        company = f"{review.shop_name} — {_place(review)}"
        Testimonial.objects.update(order=F("order") + 1)
        testimonial = Testimonial(
            order=0,
            is_published=True,
            is_featured=False,
            quote=review.text,
            author_name=review.author_name,
            author_company=company,
            avatar=review.photo.name if review.photo else "",
        )
        setattr(testimonial, f"quote_{lang}", review.text)
        setattr(testimonial, f"author_name_{lang}", review.author_name)
        setattr(testimonial, f"author_company_{lang}", company)
        testimonial.save()
        review.testimonial = testimonial
        review.save(update_fields=["testimonial"])


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0001_initial"),
        ("content", "0001_initial"),
    ]

    operations = [migrations.RunPython(publish_marked_reviews, migrations.RunPython.noop)]
