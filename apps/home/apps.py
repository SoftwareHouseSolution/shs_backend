from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HomeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.home"
    verbose_name = _("Home page")

    def ready(self):
        from apps.core.cache import watch_models

        from .models import HeroSlide, HomePage, HomeSectionItem, HomeStat

        watch_models(HomePage, HeroSlide, HomeStat, HomeSectionItem)
