from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = _("Core")

    def ready(self):
        # Imported at startup so the status page's process uptime counts from here.
        from . import system_status  # noqa: F401
