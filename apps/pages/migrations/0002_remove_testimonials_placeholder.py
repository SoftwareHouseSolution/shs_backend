"""The testimonials page shipped with a "Being prepared" placeholder block. Client reviews
now fill that page (published testimonials), so the placeholder goes. Only the untouched
seed block is removed: a block an editor rewrote is left alone."""

from django.db import migrations


def remove_placeholder(apps, schema_editor):
    PageBlock = apps.get_model("pages", "PageBlock")
    PageBlock.objects.filter(page__slug="testimonials", kind="intro", heading_en="Being prepared").delete()


class Migration(migrations.Migration):
    dependencies = [("pages", "0001_initial")]

    operations = [migrations.RunPython(remove_placeholder, migrations.RunPython.noop)]
