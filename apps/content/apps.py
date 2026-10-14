from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"
    verbose_name = _("Shared content")

    def ready(self):
        from apps.core.cache import watch_models

        from .models import ComparisonCell, ComparisonColumn, ComparisonRow, ComparisonTable, Partner, Testimonial

        watch_models(ComparisonTable, ComparisonColumn, ComparisonRow, ComparisonCell, Testimonial, Partner)
