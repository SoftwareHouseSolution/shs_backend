from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"
    verbose_name = "Shared content"

    def ready(self):
        from apps.core.cache import watch_models

        from .models import ComparisonCell, ComparisonColumn, ComparisonRow, ComparisonTable, Partner, Testimonial

        watch_models(ComparisonTable, ComparisonColumn, ComparisonRow, ComparisonCell, Testimonial, Partner)
