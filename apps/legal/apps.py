from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LegalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.legal"
    verbose_name = _("Legal pages")

    def ready(self):
        from apps.core.cache import watch_models

        from .models import LegalDocument

        watch_models(LegalDocument)
