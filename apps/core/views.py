"""Base views. Every public endpoint derives from one of these, so the envelope, the cache
and the error path are the same everywhere without a view writing any of it."""

from typing import Any

from django.db import connection
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.views import APIView

from config.api_exceptions import ServiceUnavailableException
from config.api_responses import ApiResponse

from .cache import cached_payload
from .codes import ResponseCode
from .schema import ErrorEnvelopeSerializer, api_schema, envelope


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField()


class PublicAPIView(APIView):
    """Anonymous, read-only by default, throttled by the global anon rate."""

    permission_classes: list = []


class CachedObjectView(PublicAPIView):
    """GET a single composed payload (a page, the site settings), cached per language.

    Subclasses implement `build(request, **kwargs)` and raise ResourceNotFoundException (or
    let a DoesNotExist propagate) when there is nothing to show.
    """

    cache_namespace: str = ""
    success_code = ResponseCode.CONTENT_RETRIEVED

    def build(self, request: Request, **kwargs) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError

    def get(self, request: Request, **kwargs):
        namespace = f"{self.cache_namespace}:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
        data = cached_payload(namespace, request, lambda: self.build(request, **kwargs))
        return ApiResponse.success(data, code=self.success_code)


class EnvelopeListAPIView(PublicAPIView, generics.ListAPIView):
    """A filtered, paginated list in the standard envelope, with the page cached."""

    cache_namespace: str = ""
    success_code = ResponseCode.CONTENT_LIST_RETRIEVED

    def _build_page(self) -> dict:
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is None:
            return {"data": list(self.get_serializer(queryset, many=True).data), "meta": None}
        return {
            "data": list(self.get_serializer(page, many=True).data),
            "meta": {"pagination": self.paginator.get_meta()},
        }

    def list(self, request: Request, *args, **kwargs):
        payload = (
            cached_payload(self.cache_namespace, request, self._build_page)
            if self.cache_namespace
            else self._build_page()
        )
        return ApiResponse.success(payload["data"], code=self.success_code, meta=payload["meta"])


class EnvelopeRetrieveAPIView(PublicAPIView, generics.RetrieveAPIView):
    cache_namespace: str = ""
    success_code = ResponseCode.CONTENT_RETRIEVED

    def retrieve(self, request: Request, *args, **kwargs):
        def build():
            return self.get_serializer(self.get_object()).data

        key = f"{self.cache_namespace}:{self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)}"
        data = cached_payload(key, request, build) if self.cache_namespace else build()
        return ApiResponse.success(data, code=self.success_code)


class HealthView(PublicAPIView):
    """Liveness + database check for load balancers and uptime monitors. Never cached."""

    throttle_classes: list = []

    @api_schema(
        summary="Health check",
        responses={200: envelope(HealthSerializer), 503: ErrorEnvelopeSerializer},
        tags=["system"],
    )
    def get(self, request: Request):
        try:
            connection.ensure_connection()
        except Exception as exc:  # any driver error means "not ready"
            raise ServiceUnavailableException() from exc
        return ApiResponse.success(
            {"status": "ok", "database": "ok"}, code=ResponseCode.HEALTH_OK, status=status.HTTP_200_OK
        )


class ApiNotFoundView(PublicAPIView):
    """Catch-all for unknown /api/ paths, so they 404 in the envelope even with DEBUG on
    (Django's handler404 is bypassed in debug mode)."""

    throttle_classes: list = []
    schema = None  # not an endpoint; keep it out of the OpenAPI document

    def _raise(self, request, *args, **kwargs):
        raise NotFound()

    get = post = put = patch = delete = head = options = _raise
