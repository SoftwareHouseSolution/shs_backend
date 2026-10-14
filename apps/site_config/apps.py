from django.apps import AppConfig


class SiteConfigConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.site_config"
    verbose_name = "Site"

    def ready(self):
        from apps.core.cache import watch_models

        from .models import Badge, FooterColumn, NavigationItem, SiteSettings, SocialLink

        watch_models(SiteSettings, NavigationItem, FooterColumn, SocialLink, Badge)
