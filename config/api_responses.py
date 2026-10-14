"""The one place the API response envelope is built.

Every application-controlled response — success or error, DRF view or plain Django view —
has exactly these six keys:

    {"success": bool, "message": str, "code": str, "data": ..., "errors": ..., "meta": ...}

Views never assemble that dict by hand. They call `ApiResponse.success/created/paginated`
(DRF views) and the exception handler calls `ApiResponse.error`. Code paths that run
outside DRF (URL-level 404/500 handlers, middleware) use `json_error()`, which produces
the same body as a plain Django JsonResponse.
"""

from typing import Any

from django.http import JsonResponse
from rest_framework import status as http
from rest_framework.response import Response

from apps.core.codes import ResponseCode, default_message

ENVELOPE_KEYS = ("success", "message", "code", "data", "errors", "meta")


def build_envelope(
    *,
    success: bool,
    code: ResponseCode | str,
    message: str | None = None,
    data: Any = None,
    errors: Any = None,
    meta: dict | None = None,
) -> dict:
    code = ResponseCode(code)
    return {
        "success": success,
        "message": str(message) if message is not None else default_message(code),
        "code": code.value,
        "data": data,
        "errors": errors,
        "meta": meta or None,
    }


class ApiResponse:
    """Factory for enveloped DRF responses."""

    @staticmethod
    def success(
        data: Any = None,
        *,
        code: ResponseCode = ResponseCode.CONTENT_RETRIEVED,
        message: str | None = None,
        meta: dict | None = None,
        status: int = http.HTTP_200_OK,
        headers: dict | None = None,
    ) -> Response:
        body = build_envelope(success=True, code=code, message=message, data=data, meta=meta)
        return Response(body, status=status, headers=headers)

    @staticmethod
    def created(
        data: Any = None,
        *,
        code: ResponseCode,
        message: str | None = None,
        meta: dict | None = None,
        headers: dict | None = None,
    ) -> Response:
        return ApiResponse.success(
            data, code=code, message=message, meta=meta, status=http.HTTP_201_CREATED, headers=headers
        )

    @staticmethod
    def paginated(
        data: list,
        *,
        pagination: dict,
        code: ResponseCode = ResponseCode.CONTENT_LIST_RETRIEVED,
        message: str | None = None,
        extra_meta: dict | None = None,
    ) -> Response:
        meta = {"pagination": pagination, **(extra_meta or {})}
        return ApiResponse.success(data, code=code, message=message, meta=meta)

    @staticmethod
    def error(
        *,
        code: ResponseCode,
        status: int,
        message: str | None = None,
        errors: Any = None,
        meta: dict | None = None,
        headers: dict | None = None,
    ) -> Response:
        body = build_envelope(success=False, code=code, message=message, errors=errors, meta=meta)
        return Response(body, status=status, headers=headers)


def json_error(
    *,
    code: ResponseCode,
    status: int,
    message: str | None = None,
    errors: Any = None,
    meta: dict | None = None,
) -> JsonResponse:
    """The error envelope for code that runs outside DRF's request cycle."""
    body = build_envelope(success=False, code=code, message=message, errors=errors, meta=meta)
    return JsonResponse(body, status=status, json_dumps_params={"ensure_ascii": False})
