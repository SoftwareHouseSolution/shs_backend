"""OpenAPI helpers: describe the envelope once and reuse it for every endpoint, so the
generated docs show exactly what the handler and the response factory produce."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers

from .codes import ResponseCode

LANG_PARAMETER = OpenApiParameter(
    name="lang",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    enum=["en", "ar"],
    required=False,
    description=(
        "Response language. Overrides Accept-Language. Missing translations fall back to "
        "the other language. An unsupported value returns 400 UNSUPPORTED_LANGUAGE."
    ),
)

_cache: dict[str, type[serializers.Serializer]] = {}


def envelope(inner, *, name: str | None = None, many: bool = False) -> type[serializers.Serializer]:
    """A documentation-only serializer for `{success, message, code, data: inner, …}`."""
    inner_name = inner.__name__.removesuffix("Serializer")
    name = name or f"{inner_name}{'List' if many else ''}Envelope"
    if name not in _cache:
        _cache[name] = type(
            name,
            (serializers.Serializer,),
            {
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
                "code": serializers.ChoiceField(choices=[c.value for c in ResponseCode]),
                "data": inner(many=many),
                "errors": serializers.JSONField(allow_null=True),
                "meta": serializers.JSONField(allow_null=True),
            },
        )
    return _cache[name]


class ErrorEnvelopeSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    message = serializers.CharField()
    code = serializers.ChoiceField(choices=[c.value for c in ResponseCode])
    data = serializers.JSONField(allow_null=True, default=None)
    errors = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        allow_null=True,
        help_text="Field name → list of messages. Present for VALIDATION_ERROR.",
    )
    meta = serializers.DictField(
        allow_null=True,
        help_text="`request_id` on 5xx responses; `retry_after` (seconds) on 429.",
    )


def _error(description: str, code: ResponseCode, example: dict) -> OpenApiResponse:
    return OpenApiResponse(
        response=ErrorEnvelopeSerializer,
        description=description,
        examples=[
            OpenApiExample(
                code.value,
                value={
                    "success": False,
                    "message": example.get("message", ""),
                    "code": code.value,
                    "data": None,
                    "errors": example.get("errors"),
                    "meta": example.get("meta"),
                },
                response_only=True,
            )
        ],
    )


ERROR_400_LANG = _error(
    "Unsupported `lang` value.",
    ResponseCode.UNSUPPORTED_LANGUAGE,
    {"message": "The requested language is not supported.", "errors": {"lang": ["“fr” is not supported. Use one of: en, ar."]}},
)
ERROR_400_VALIDATION = _error(
    "Validation failed. `errors` maps each field to its messages.",
    ResponseCode.VALIDATION_ERROR,
    {"message": "The submitted data is invalid.", "errors": {"email": ["Enter a valid email address."]}},
)
ERROR_404 = _error(
    "Not found, or not published.",
    ResponseCode.RESOURCE_NOT_FOUND,
    {"message": "The requested resource was not found."},
)
ERROR_409 = _error(
    "Duplicate submission.",
    ResponseCode.DUPLICATE_ENQUIRY,
    {"message": "We have already received this message. There is no need to send it again."},
)
ERROR_415 = _error(
    "Body is not JSON.",
    ResponseCode.UNSUPPORTED_MEDIA_TYPE,
    {"message": "The request body format is not supported. Send JSON."},
)
ERROR_429 = _error(
    "Rate limit exceeded. Also sent as the Retry-After header.",
    ResponseCode.RATE_LIMIT_EXCEEDED,
    {"message": "Too many requests. Please wait a moment and try again.", "meta": {"retry_after": 42}},
)
ERROR_500 = _error(
    "Unexpected failure. Quote `meta.request_id` to support.",
    ResponseCode.INTERNAL_SERVER_ERROR,
    {"message": "An unexpected error occurred.", "meta": {"request_id": "3f2c9a0e8b8d4c7f9a1e2b3c4d5e6f70"}},
)


def api_schema(*, summary: str, responses: dict, parameters: list | None = None, **kwargs):
    """extend_schema with the language parameter and the errors every endpoint can return."""
    return extend_schema(
        summary=summary,
        parameters=[LANG_PARAMETER, *(parameters or [])],
        responses={**responses, 400: responses.get(400, ERROR_400_LANG), 429: ERROR_429, 500: ERROR_500},
        **kwargs,
    )
