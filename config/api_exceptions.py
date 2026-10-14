"""Application exception hierarchy and the global DRF exception handler.

Services raise the exceptions defined here for *expected* failures (a missing record, a
duplicate submission, a broken business rule). Views do not catch them; DRF routes every
exception raised during a request through `api_exception_handler`, which turns it into the
standard error envelope with the right HTTP status and a stable code.

Anything the handler does not recognise is an *unexpected* failure: it is logged once,
with the request id and full traceback, and the client receives a generic 500 that
reveals nothing about the cause — only the request id to quote to support.
"""

import logging
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, OperationalError
from django.http import Http404
from rest_framework import exceptions as drf
from rest_framework import status as http
from rest_framework.response import Response
from rest_framework.serializers import as_serializer_error

from apps.core.codes import ResponseCode
from apps.core.request_context import current_request_id

from .api_responses import ApiResponse

logger = logging.getLogger("config.api_exceptions")


# ── Hierarchy ────────────────────────────────────────────────────────────────────────


class ApplicationException(Exception):
    """Base for every expected, client-reportable failure.

    Subclasses set three class attributes; callers may override the message, the code
    (to a more specific one in the same family), and attach structured `errors`/`meta`.
    """

    status_code: int = http.HTTP_400_BAD_REQUEST
    code: ResponseCode = ResponseCode.BUSINESS_RULE_VIOLATION
    default_message: Any = None  # falls back to the code's catalogue message

    def __init__(
        self,
        message: Any = None,
        *,
        code: ResponseCode | None = None,
        errors: Any = None,
        meta: dict | None = None,
    ):
        self.code = code or self.code
        self.message = message if message is not None else self.default_message
        self.errors = errors
        self.meta = meta
        super().__init__(str(self.message) if self.message is not None else self.code)


class BusinessRuleException(ApplicationException):
    """The request was well-formed but breaks a domain rule."""

    status_code = http.HTTP_422_UNPROCESSABLE_ENTITY
    code = ResponseCode.BUSINESS_RULE_VIOLATION


class ResourceNotFoundException(ApplicationException):
    status_code = http.HTTP_404_NOT_FOUND
    code = ResponseCode.RESOURCE_NOT_FOUND


class ResourceConflictException(ApplicationException):
    status_code = http.HTTP_409_CONFLICT
    code = ResponseCode.RESOURCE_CONFLICT


class PermissionDeniedException(ApplicationException):
    status_code = http.HTTP_403_FORBIDDEN
    code = ResponseCode.PERMISSION_DENIED


class ExternalServiceException(ApplicationException):
    """A dependency (mail server, third-party API) failed. Raised by adapters."""

    status_code = http.HTTP_502_BAD_GATEWAY
    code = ResponseCode.EXTERNAL_SERVICE_ERROR


class ServiceUnavailableException(ApplicationException):
    status_code = http.HTTP_503_SERVICE_UNAVAILABLE
    code = ResponseCode.SERVICE_UNAVAILABLE


# ── Framework exception → (code, public message) ─────────────────────────────────────
# Order matters: the first isinstance match wins, so subclasses precede their bases.
_DRF_CODES: tuple[tuple[type[drf.APIException], ResponseCode], ...] = (
    (drf.ValidationError, ResponseCode.VALIDATION_ERROR),
    (drf.ParseError, ResponseCode.MALFORMED_REQUEST),
    (drf.NotAuthenticated, ResponseCode.AUTHENTICATION_REQUIRED),
    (drf.AuthenticationFailed, ResponseCode.AUTHENTICATION_FAILED),
    (drf.PermissionDenied, ResponseCode.PERMISSION_DENIED),
    (drf.NotFound, ResponseCode.RESOURCE_NOT_FOUND),
    (drf.MethodNotAllowed, ResponseCode.METHOD_NOT_ALLOWED),
    (drf.NotAcceptable, ResponseCode.NOT_ACCEPTABLE),
    (drf.UnsupportedMediaType, ResponseCode.UNSUPPORTED_MEDIA_TYPE),
    (drf.Throttled, ResponseCode.RATE_LIMIT_EXCEEDED),
)


def _translate_framework_exception(exc: Exception) -> Exception:
    """Map Django and database exceptions onto their DRF/application equivalents so the
    rest of the handler only has two families to consider."""
    if isinstance(exc, (Http404, ObjectDoesNotExist)):
        return drf.NotFound()
    if isinstance(exc, DjangoPermissionDenied):
        return drf.PermissionDenied()
    if isinstance(exc, DjangoValidationError):
        return drf.ValidationError(as_serializer_error(exc))
    if isinstance(exc, IntegrityError):
        # Never echo the database message: it names tables, columns and values.
        logger.warning("Integrity error translated to 409: %s", exc.__class__.__name__)
        return ResourceConflictException()
    if isinstance(exc, OperationalError):
        logger.error("Database unavailable", exc_info=exc)
        return ServiceUnavailableException()
    return exc


def _headers_for(exc: drf.APIException) -> dict:
    headers = {}
    if getattr(exc, "auth_header", None):
        headers["WWW-Authenticate"] = exc.auth_header
    if getattr(exc, "wait", None):
        headers["Retry-After"] = str(int(exc.wait))
    return headers


def _response_for_drf(exc: drf.APIException) -> Response:
    code = next((c for cls, c in _DRF_CODES if isinstance(exc, cls)), None)
    if code is None:
        # A DRF exception we have no specific code for (e.g. a custom APIException from a
        # third-party package). Keep its status; describe it generically.
        code = (
            ResponseCode.INTERNAL_SERVER_ERROR
            if exc.status_code >= 500
            else ResponseCode.BUSINESS_RULE_VIOLATION
        )

    errors = None
    meta = None
    if isinstance(exc, drf.ValidationError):
        detail = exc.detail
        # A bare list (raised from validate()) is a non-field error; give it a stable key
        # so `errors` is always an object keyed by field.
        errors = detail if isinstance(detail, dict) else {"non_field_errors": detail}
    elif isinstance(exc, drf.Throttled) and exc.wait is not None:
        meta = {"retry_after": int(exc.wait)}

    return ApiResponse.error(
        code=code, status=exc.status_code, errors=errors, meta=meta, headers=_headers_for(exc)
    )


def internal_error_meta() -> dict:
    return {"request_id": current_request_id()}


def api_exception_handler(exc: Exception, context: dict) -> Response:
    """DRF's EXCEPTION_HANDLER. Always returns an enveloped response — never None — so no
    exception escapes to Django's HTML 500 page from inside an API view."""
    exc = _translate_framework_exception(exc)

    if isinstance(exc, ApplicationException):
        meta = exc.meta
        if exc.status_code >= 500:
            meta = {**(meta or {}), **internal_error_meta()}
        return ApiResponse.error(
            code=exc.code, status=exc.status_code, message=exc.message, errors=exc.errors, meta=meta
        )

    if isinstance(exc, drf.APIException):
        return _response_for_drf(exc)

    view = context.get("view")
    logger.exception(
        "Unhandled exception in %s",
        view.__class__.__name__ if view else "API view",
        exc_info=exc,
    )
    return ApiResponse.error(
        code=ResponseCode.INTERNAL_SERVER_ERROR,
        status=http.HTTP_500_INTERNAL_SERVER_ERROR,
        meta=internal_error_meta(),
    )


__all__ = [
    "ApplicationException",
    "BusinessRuleException",
    "ResourceNotFoundException",
    "ResourceConflictException",
    "PermissionDeniedException",
    "ExternalServiceException",
    "ServiceUnavailableException",
    "api_exception_handler",
    "internal_error_meta",
]
