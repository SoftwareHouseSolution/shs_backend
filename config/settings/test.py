"""Test run: PostgreSQL (the production engine), isolated cache, fast hashing, no e-mail."""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, REST_FRAMEWORK

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "tests"}}
MEDIA_ROOT = BASE_DIR / ".test-media"
MEDIA_PUBLIC_BASE_URL = ""
STORAGES = {
    "default": {"BACKEND": "apps.core.storage.DeduplicatingFileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
ENQUIRY_NOTIFIER = "apps.enquiries.notifiers.NullEnquiryNotifier"
# Generous by default so ordinary tests never trip the limiter; throttle tests override it.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"anon": "10000/min", "enquiries": "1000/min", "analytics": "10000/min"},
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.core.logging.RequestIdFilter"}},
    "handlers": {"null": {"class": "logging.NullHandler", "filters": ["request_id"]}},
    "root": {"handlers": ["null"], "level": "WARNING"},
}
