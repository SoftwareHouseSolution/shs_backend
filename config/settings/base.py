"""Settings shared by every environment.

Environment-specific modules (dev, test, prod) import * from here and override only what
differs. Every secret and every host-specific value is read from the environment (or a
local `.env` file in development) — nothing sensitive is committed. See `.env.example`.
"""

from pathlib import Path

import environ
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# A local .env is a development convenience; in production the real environment wins.
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# ── Applications ─────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # modeltranslation must precede django.contrib.admin so its admin patches apply.
    "modeltranslation",
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "corsheaders",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    # Project
    "apps.core",
    "apps.site_config",
    "apps.content",
    "apps.home",
    "apps.pages",
    "apps.clients",
    "apps.events",
    "apps.enquiries",
    "apps.reviews",
    "apps.analytics",
]

MIDDLEWARE = [
    # First, so every later log line and every response — including errors raised by
    # other middleware — carries the request id.
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # The admin's language: the editor's choice (language switcher → cookie), else the
    # browser's Accept-Language, else LANGUAGE_CODE.
    "django.middleware.locale.LocaleMiddleware",
    # The API's language (?lang=, then Accept-Language). Runs after LocaleMiddleware and
    # overrides it for /api/, so an editor's admin language never leaks into API responses.
    "apps.core.middleware.ApiLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ApiExceptionMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ── Database ─────────────────────────────────────────────────────────────────────────
# DATABASE_URL, e.g. postgres://user:password@localhost:5432/shs_backend
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"]["ATOMIC_REQUESTS"] = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Cache ────────────────────────────────────────────────────────────────────────────
# Local memory by default. Point CACHE_URL at Redis (redis://…) in production so the
# content cache and the rate limiter are shared between worker processes.
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://shs-content")}
CONTENT_CACHE_TIMEOUT = env.int("CONTENT_CACHE_TIMEOUT", default=300)

# ── Auth ─────────────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# The admin is the only login on this site. Without this, signing in at /admin/login/
# directly (no ?next=) lands on Django's default /accounts/profile/, which is a 404.
LOGIN_URL = reverse_lazy("admin:login")
LOGIN_REDIRECT_URL = reverse_lazy("admin:index")

# ── Internationalisation ─────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ar", "العربية")]
LANGUAGE_DIRECTIONS = {"en": "ltr", "ar": "rtl"}
LOCALE_PATHS = [BASE_DIR / "apps" / "core" / "locale"]
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True

# Translated model fields (title_en, title_ar, …).
MODELTRANSLATION_DEFAULT_LANGUAGE = "en"
MODELTRANSLATION_LANGUAGES = ("en", "ar")
# Fallback policy, documented in README: a missing Arabic value falls back to English and a
# missing English value falls back to Arabic, so the API never returns an empty string for
# content that exists in the other language.
MODELTRANSLATION_FALLBACK_LANGUAGES = {"default": ("en",), "en": ("ar",), "ar": ("en",)}
MODELTRANSLATION_AUTO_POPULATE = False

# ── Static and media ─────────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = env("DJANGO_MEDIA_URL", default="/media/")
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", default=str(BASE_DIR / "media")))
# Absolute origin the browser should load media from (e.g. https://cms.example.com). When
# unset, URLs are built from the incoming request's host, which is right in development
# and wrong behind an internal hostname — set it in production.
MEDIA_PUBLIC_BASE_URL = env("MEDIA_PUBLIC_BASE_URL", default="")
# Where Admin → System status → Clean up unused files sets files aside. Empty: a hidden
# MEDIA_ROOT/.trash (then deny /media/.trash/ in the web server). Docker uses a separate
# volume, so the web server never sees it.
MEDIA_TRASH_ROOT = env("DJANGO_MEDIA_TRASH_ROOT", default="")

# Media: an upload identical to a stored file reuses it instead of adding a copy
# (apps.core.storage; existing files are indexed with `manage.py index_media`).
STORAGES = {
    "default": {"BACKEND": "apps.core.storage.DeduplicatingFileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Upload limits, enforced by apps.core.validators. Django's own limit below covers the
# request body as a whole.
MAX_IMAGE_UPLOAD_MB = env.int("MAX_IMAGE_UPLOAD_MB", default=8)
MAX_VIDEO_UPLOAD_MB = env.int("MAX_VIDEO_UPLOAD_MB", default=60)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o644

# ── CORS / CSRF ──────────────────────────────────────────────────────────────────────
# The public site calls the API from the browser (enquiry form) — list its origins.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_URLS_REGEX = r"^/api/.*$"
CORS_ALLOW_CREDENTIALS = False
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Content-Language", "Retry-After"]
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ── Django REST Framework ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # The public API is anonymous. Content management happens in the admin, which has
    # its own session auth; no API endpoint accepts a session, so none needs CSRF.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("API_THROTTLE_ANON", default="600/min"),
        "enquiries": env("API_THROTTLE_ENQUIRIES", default="5/hour"),
        "reviews": env("API_THROTTLE_REVIEWS", default="5/hour"),
        # Each draft is a paid model call: generous for a client trying a few versions,
        # tight enough that nobody can run up the bill.
        "review_drafts": env("API_THROTTLE_REVIEW_DRAFTS", default="30/hour"),
        # A page reports on open, every 15s while visible, and on leave.
        "analytics": env("API_THROTTLE_ANALYTICS", default="120/min"),
    },
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "config.api_exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Software House Solutions — Content API",
    "DESCRIPTION": (
        "Public, read-mostly API that powers the bilingual SWH website.\n\n"
        "**Envelope.** Every response — success or error — has the same six fields: "
        "`success`, `message`, `code`, `data`, `errors`, `meta`.\n\n"
        "**Language.** Pass `?lang=en` or `?lang=ar`. Without it the `Accept-Language` "
        "header is used, then English. Missing translations fall back to the other language. "
        "The resolved language is echoed in the `Content-Language` header.\n\n"
        "**Errors.** `code` is a stable machine-readable value (see the `ErrorCode` schema); "
        "`message` is localised and safe to show. `errors` carries field-level validation "
        "messages keyed by field name. Every response carries an `X-Request-ID` header; "
        "500 responses also return it in `meta.request_id`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "ResponseCodeEnum": "apps.core.codes.ResponseCode",
        # Support and updates share one rating scale.
        "ReviewRatingEnum": "apps.reviews.models.ReviewRating",
    },
}

# ── Application settings ─────────────────────────────────────────────────────────────
# Dotted path of the class that is told about new enquiries (Adapter, see
# apps.enquiries.notifiers). Swap for NullEnquiryNotifier to disable e-mail.
ENQUIRY_NOTIFIER = env(
    "ENQUIRY_NOTIFIER", default="apps.enquiries.notifiers.EmailEnquiryNotifier"
)
ENQUIRY_NOTIFICATION_EMAIL = env("ENQUIRY_NOTIFICATION_EMAIL", default="")
# AI-drafted client reviews (apps.reviews.drafting). Off while ANTHROPIC_API_KEY is empty:
# the review page then drafts from its own templates.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
REVIEW_AI_MODEL = env("REVIEW_AI_MODEL", default="claude-opus-5-5")
REVIEW_AI_TIMEOUT = env.float("REVIEW_AI_TIMEOUT", default=30.0)
# Who is told about a new client review (apps.reviews.notifiers); same address as enquiries.
REVIEW_NOTIFIER = env("REVIEW_NOTIFIER", default="apps.reviews.notifiers.EmailReviewNotifier")
# A second identical enquiry from the same address inside this window is a 409.
ENQUIRY_DUPLICATE_WINDOW_MINUTES = env.int("ENQUIRY_DUPLICATE_WINDOW_MINUTES", default=10)

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@softwarehouse-sol.com")

# Visits older than this are deleted by `manage.py prune_analytics` (schedule it daily).
ANALYTICS_RETENTION_DAYS = env.int("ANALYTICS_RETENTION_DAYS", default=180)

ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")
# Where "View site" in the admin points.
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# ── Logging ──────────────────────────────────────────────────────────────────────────
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_FORMAT = env("LOG_FORMAT", default="text")  # "text" or "json"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.core.logging.RequestIdFilter"}},
    "formatters": {
        "text": {"format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"},
        "json": {"()": "apps.core.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": LOG_FORMAT,
        },
        # Errors only: feeds "Recent errors" on Admin → System status.
        "recent_errors": {
            "()": "apps.core.system_status.RecentErrorsHandler",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console", "recent_errors"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console", "recent_errors"], "level": LOG_LEVEL, "propagate": False},
        # Requests are logged by our own exception handler with the request id; Django's
        # duplicate 4xx/5xx lines add noise without context.
        "django.request": {"handlers": ["console", "recent_errors"], "level": "ERROR", "propagate": False},
        "apps": {"handlers": ["console", "recent_errors"], "level": LOG_LEVEL, "propagate": False},
        "config": {"handlers": ["console", "recent_errors"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ── Admin (Unfold) ───────────────────────────────────────────────────────────────────
UNFOLD = {
    "SITE_TITLE": "SWH CMS",
    "SITE_HEADER": "Software House Solutions",
    "SITE_SUBHEADER": _("Website content"),
    "SITE_URL": FRONTEND_URL,
    # The site's logo: ink on the light theme, white on the dark one.
    "SITE_ICON": {
        "light": lambda request: static("core/brand/swh-logo-ink.png"),
        "dark": lambda request: static("core/brand/swh-logo.png"),
    },
    "SITE_FAVICONS": [
        {"rel": "icon", "type": "image/png", "href": lambda request: static("core/brand/swh-logo-ink.png")},
    ],
    # Opened from the logo at the top of the sidebar.
    "SITE_DROPDOWN": [
        {"title": _("View website"), "icon": "open_in_new", "link": FRONTEND_URL, "attrs": {"target": "_blank"}},
        {"title": _("API documentation"), "icon": "api", "link": reverse_lazy("api-v1:docs"), "attrs": {"target": "_blank"}},
    ],
    "SHOW_HISTORY": True,
    "SHOW_BACK_BUTTON": True,
    # Language switcher in the user menu (posts to /i18n/setlang/).
    "SHOW_LANGUAGES": True,
    "SHOW_VIEW_ON_SITE": True,
    "BORDER_RADIUS": "8px",
    "ENVIRONMENT": "apps.core.admin_utils.environment_callback",
    "DASHBOARD_CALLBACK": "apps.core.admin_utils.dashboard_callback",
    "STYLES": [lambda request: static("core/admin.css")],
    "LOGIN": {"image": lambda request: static("core/brand/login-panel.svg")},
    # Ctrl+K also finds records, not only admin pages.
    "COMMAND": {"search_models": True, "show_history": True},
    "COLORS": {
        # Neutrals: a cool slate that sits with the brand blue.
        "base": {
            "50": "#f8fafc",
            "100": "#f1f5f9",
            "200": "#e2e8f0",
            "300": "#cbd5e1",
            "400": "#94a3b8",
            "500": "#64748b",
            "600": "#475569",
            "700": "#334155",
            "800": "#1e293b",
            "900": "#0f172a",
            "950": "#020617",
        },
        # The site's accent (#4A6FA6) as the admin's primary scale.
        "primary": {
            "50": "#eff4fa",
            "100": "#dce6f3",
            "200": "#bccfe8",
            "300": "#93b1d8",
            "400": "#6f93c4",
            "500": "#4a6fa6",
            "600": "#3a5a8a",
            "700": "#314b72",
            "800": "#2b405f",
            "900": "#263750",
            "950": "#182234",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Site"),
                "items": [
                    {"title": _("Dashboard"), "icon": "dashboard", "link": reverse_lazy("admin:index")},
                    {"title": _("Site settings"), "icon": "settings", "link": reverse_lazy("admin:site_config_sitesettings_changelist")},
                    {"title": _("Navigation"), "icon": "menu", "link": reverse_lazy("admin:site_config_navigationitem_changelist")},
                    {"title": _("Footer columns"), "icon": "view_column", "link": reverse_lazy("admin:site_config_footercolumn_changelist")},
                    {"title": _("Social links"), "icon": "share", "link": reverse_lazy("admin:site_config_sociallink_changelist")},
                    {"title": _("Badges"), "icon": "verified", "link": reverse_lazy("admin:site_config_badge_changelist")},
                ],
            },
            {
                "title": _("Pages"),
                "items": [
                    {"title": _("Home page"), "icon": "home", "link": reverse_lazy("admin:home_homepage_changelist")},
                    {"title": _("Interior pages"), "icon": "description", "link": reverse_lazy("admin:pages_page_changelist")},
                ],
            },
            {
                "title": _("Shared content"),
                "items": [
                    {"title": _("Testimonials"), "icon": "format_quote", "link": reverse_lazy("admin:content_testimonial_changelist")},
                    {"title": _("Comparison tables"), "icon": "table_chart", "link": reverse_lazy("admin:content_comparisontable_changelist")},
                    {"title": _("Partners"), "icon": "handshake", "link": reverse_lazy("admin:content_partner_changelist")},
                    {"title": _("Events"), "icon": "event", "link": reverse_lazy("admin:events_event_changelist")},
                ],
            },
            {
                "title": _("Clients"),
                "items": [
                    {"title": _("Clients"), "icon": "storefront", "link": reverse_lazy("admin:clients_client_changelist")},
                    {"title": _("Regions"), "icon": "map", "link": reverse_lazy("admin:clients_region_changelist")},
                    {"title": _("Sectors"), "icon": "category", "link": reverse_lazy("admin:clients_sector_changelist")},
                    {"title": _("Business types"), "icon": "sell", "link": reverse_lazy("admin:clients_businesstype_changelist")},
                ],
            },
            {
                "title": _("Inbox"),
                "items": [
                    {
                        "title": _("Enquiries"),
                        "icon": "inbox",
                        "link": reverse_lazy("admin:enquiries_enquiry_changelist"),
                        "badge": "apps.enquiries.admin.new_enquiry_badge",
                    },
                    {
                        "title": _("Client reviews"),
                        "icon": "reviews",
                        "link": reverse_lazy("admin:reviews_review_changelist"),
                        "badge": "apps.reviews.admin.new_review_badge",
                    },
                ],
            },
            {
                "title": _("Visitors"),
                "items": [
                    {"title": _("Visit analysis"), "icon": "monitoring", "link": reverse_lazy("admin:analytics_visitsession_analysis")},
                    {
                        "title": _("Visits"),
                        "icon": "timeline",
                        "link": reverse_lazy("admin:analytics_visitsession_changelist"),
                        "active": "apps.analytics.admin.visits_nav_active",
                    },
                    {"title": _("Page views"), "icon": "visibility", "link": reverse_lazy("admin:analytics_pageview_changelist")},
                ],
            },
            {
                "title": _("Access"),
                "items": [
                    {"title": _("Users"), "icon": "person", "link": reverse_lazy("admin:auth_user_changelist")},
                    {"title": _("Groups"), "icon": "group", "link": reverse_lazy("admin:auth_group_changelist")},
                ],
            },
            {
                "title": _("System"),
                "items": [
                    {
                        "title": _("System status"),
                        "icon": "monitor_heart",
                        "link": reverse_lazy("admin-system-status"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                ],
            },
        ],
    },
}
