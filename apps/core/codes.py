"""Stable, machine-readable application codes and their default public messages.

A code is part of the API contract: the frontend branches on it, so once published it is
never renamed or reused for a different meaning. Messages, by contrast, are for people —
they are localised (gettext, see apps/core/locale) and may be reworded freely.

HTTP status and application code are deliberately separate axes: two 409s can carry
different codes (RESOURCE_CONFLICT, DUPLICATE_ENQUIRY) so a client can tell them apart.
"""

from enum import StrEnum

from django.utils.translation import gettext_lazy as _


class ResponseCode(StrEnum):
    # ── Success ──────────────────────────────────────────────────────────────────
    CONTENT_RETRIEVED = "CONTENT_RETRIEVED"
    CONTENT_LIST_RETRIEVED = "CONTENT_LIST_RETRIEVED"
    ENQUIRY_CREATED = "ENQUIRY_CREATED"
    REVIEW_CREATED = "REVIEW_CREATED"
    ANALYTICS_EVENT_ACCEPTED = "ANALYTICS_EVENT_ACCEPTED"
    HEALTH_OK = "HEALTH_OK"

    # ── Client errors ────────────────────────────────────────────────────────────
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    NOT_ACCEPTABLE = "NOT_ACCEPTABLE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    DUPLICATE_ENQUIRY = "DUPLICATE_ENQUIRY"
    DUPLICATE_REVIEW = "DUPLICATE_REVIEW"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # ── Server errors ────────────────────────────────────────────────────────────
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


DEFAULT_MESSAGES = {
    ResponseCode.CONTENT_RETRIEVED: _("Content retrieved successfully."),
    ResponseCode.CONTENT_LIST_RETRIEVED: _("Content retrieved successfully."),
    ResponseCode.ENQUIRY_CREATED: _("Thank you — your message has been received. We will be in touch soon."),
    ResponseCode.REVIEW_CREATED: _("Thank you! Your review has reached us. It means a lot to us."),
    ResponseCode.ANALYTICS_EVENT_ACCEPTED: _("Event recorded."),
    ResponseCode.HEALTH_OK: _("Service is healthy."),
    ResponseCode.VALIDATION_ERROR: _("The submitted data is invalid."),
    ResponseCode.MALFORMED_REQUEST: _("The request could not be read. Check that the body is valid JSON."),
    ResponseCode.UNSUPPORTED_LANGUAGE: _("The requested language is not supported."),
    ResponseCode.AUTHENTICATION_REQUIRED: _("Authentication is required to access this resource."),
    ResponseCode.AUTHENTICATION_FAILED: _("The supplied credentials are invalid."),
    ResponseCode.PERMISSION_DENIED: _("You do not have permission to perform this action."),
    ResponseCode.RESOURCE_NOT_FOUND: _("The requested resource was not found."),
    ResponseCode.METHOD_NOT_ALLOWED: _("This method is not allowed for the requested resource."),
    ResponseCode.NOT_ACCEPTABLE: _("The requested response format is not available."),
    ResponseCode.UNSUPPORTED_MEDIA_TYPE: _("The request body format is not supported. Send JSON."),
    ResponseCode.RESOURCE_CONFLICT: _("The request conflicts with the current state of the resource."),
    ResponseCode.DUPLICATE_ENQUIRY: _("We have already received this message. There is no need to send it again."),
    ResponseCode.DUPLICATE_REVIEW: _("We have already received this review. Thank you!"),
    ResponseCode.BUSINESS_RULE_VIOLATION: _("The request could not be completed."),
    ResponseCode.RATE_LIMIT_EXCEEDED: _("Too many requests. Please wait a moment and try again."),
    ResponseCode.EXTERNAL_SERVICE_ERROR: _("A service we depend on did not respond. Please try again shortly."),
    ResponseCode.SERVICE_UNAVAILABLE: _("The service is temporarily unavailable. Please try again shortly."),
    ResponseCode.INTERNAL_SERVER_ERROR: _("An unexpected error occurred."),
}


def default_message(code: ResponseCode) -> str:
    """The localised default message for a code, resolved in the active language."""
    return str(DEFAULT_MESSAGES[code])
