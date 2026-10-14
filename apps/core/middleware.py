"""Request-scoped middleware: request ids, API language activation, and a JSON safety net
for exceptions raised by non-DRF views under /api/."""

import logging

from django.http import HttpRequest, HttpResponse
from django.utils import translation
from django.utils.translation import gettext as _
from rest_framework import status as http

from config.api_exceptions import internal_error_meta
from config.api_responses import json_error

from .codes import ResponseCode
from .i18n import UnsupportedLanguage, direction, resolve_language, supported_languages
from .request_context import accept_or_create_request_id, request_id_var

logger = logging.getLogger("apps.core.middleware")

API_PREFIX = "/api/"


def is_api_request(request: HttpRequest) -> bool:
    return request.path.startswith(API_PREFIX)


class RequestIdMiddleware:
    """Assigns every request an id (or accepts a well-formed inbound X-Request-ID), exposes
    it to logging through a context variable, and echoes it in the response header so a
    user-visible error can be matched to its log line."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = accept_or_create_request_id(request.headers.get("X-Request-ID"))
        request.request_id = request_id
        # Deliberately not reset afterwards: Django logs a 5xx response ("Internal Server
        # Error" on django.request) only after the whole middleware chain has returned, and
        # that line must carry the id too. Every request overwrites the value on entry, and
        # under ASGI each request runs in its own context copy, so nothing leaks between them.
        request_id_var.set(request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class ApiLanguageMiddleware:
    """Activates the resolved language for API requests only.

    Content (via modeltranslation), DRF's own validation messages and our message catalogue
    all read the active language, so activating it once here localises the whole response.
    The admin and every other non-API path are left on LANGUAGE_CODE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not is_api_request(request):
            return self.get_response(request)

        try:
            resolution = resolve_language(request)
        except UnsupportedLanguage as exc:
            detail = _("“%(value)s” is not supported. Use one of: %(choices)s.") % {
                "value": exc.requested[:16],
                "choices": ", ".join(supported_languages()),
            }
            return json_error(
                code=ResponseCode.UNSUPPORTED_LANGUAGE,
                status=http.HTTP_400_BAD_REQUEST,
                errors={"lang": [detail]},
            )

        request.LANGUAGE_CODE = resolution.language
        with translation.override(resolution.language):
            response = self.get_response(request)
        response["Content-Language"] = resolution.language
        response["X-Content-Direction"] = direction(resolution.language)
        # The same URL answers differently per Accept-Language unless ?lang= pins it.
        vary = response.get("Vary")
        if "Accept-Language" not in (vary or ""):
            response["Vary"] = f"{vary}, Accept-Language" if vary else "Accept-Language"
        return response


class ApiExceptionMiddleware:
    """Last line of defence for /api/ paths served by plain Django views (DRF views never
    reach this — their exceptions go through api_exception_handler). Guarantees an API
    client never receives Django's HTML error page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(self, request: HttpRequest, exception: Exception):
        if not is_api_request(request):
            return None
        logger.exception("Unhandled exception outside DRF on %s", request.path, exc_info=exception)
        return json_error(
            code=ResponseCode.INTERNAL_SERVER_ERROR,
            status=http.HTTP_500_INTERNAL_SERVER_ERROR,
            meta=internal_error_meta(),
        )
