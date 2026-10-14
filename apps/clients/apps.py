from django.apps import AppConfig


class ClientsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.clients"
    verbose_name = "Clients"

    def ready(self):
        from apps.core.cache import watch_models

        from .models import BusinessType, Client, Region, Sector

        watch_models(Region, Sector, BusinessType, Client)
