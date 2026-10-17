"""Local development: DEBUG on, permissive hosts, console e-mail."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
# 3000: `pnpm dev`. 3001 and 3311: the production builds the frontend's tools/check-*.mjs
# scripts run against. The site posts enquiries and visit analytics from these origins.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://localhost:3311"],
)

# Plain storage in development: the manifest storage needs collectstatic to have run.
STORAGES = {
    "default": {"BACKEND": "apps.core.storage.DeduplicatingFileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
