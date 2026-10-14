from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"
    verbose_name = _("News & events")

    def ready(self):
        from apps.core.cache import watch_models

        from .models import Event, EventPhoto

        watch_models(Event, EventPhoto)
