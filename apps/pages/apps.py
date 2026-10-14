from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pages"
    verbose_name = _("Pages")

    def ready(self):
        from apps.core.cache import watch_models

        from .models import BlockItem, Page, PageBlock

        watch_models(Page, PageBlock, BlockItem)
