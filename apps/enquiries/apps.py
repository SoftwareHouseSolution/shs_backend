from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EnquiriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.enquiries"
    verbose_name = _("Enquiries")
