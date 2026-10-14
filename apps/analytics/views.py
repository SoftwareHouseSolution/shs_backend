from urllib.parse import urlparse

from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.throttling import ScopedRateThrottle

from apps.core.codes import ResponseCode
from apps.core.schema import ERROR_400_VALIDATION, ERROR_415, api_schema, envelope
from apps.core.views import PublicAPIView
from config.api_responses import ApiResponse

from .serializers import ViewReportSerializer
from .services import AnalyticsService, ViewReport


class BeaconJSONParser(JSONParser):
    """navigator.sendBeacon can only send CORS-safelisted content types without a
    preflight, so the site sends its JSON as text/plain. Same parsing, other media type."""

    media_type = "text/plain"


class CollectView(PublicAPIView):
    """Page-view reports from the website. Answers 202 whether or not the report was kept
    (bot traffic is dropped silently) — the browser does not act on the result."""

    parser_classes = [JSONParser, BeaconJSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analytics"
    service_factory = staticmethod(AnalyticsService)

    @api_schema(
        summary="Record a page view or update its time on page",
        request=ViewReportSerializer,
        responses={202: envelope(ViewReportSerializer, name="AnalyticsAcceptedEnvelope"), 400: ERROR_400_VALIDATION, 415: ERROR_415},
        tags=["analytics"],
        description=(
            "Idempotent per `view_id`: send it when a page opens (duration 0), while it is "
            "visible, and when it is left. Duration only grows. Accepts `application/json` "
            "or `text/plain` (for navigator.sendBeacon). `data` is always null."
        ),
    )
    def post(self, request):
        serializer = ViewReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.service_factory().record(
            ViewReport(**serializer.validated_data),
            user_agent=request.headers.get("User-Agent", ""),
            site_host=_host_of(request.headers.get("Origin", "")),
        )
        return ApiResponse.success(None, code=ResponseCode.ANALYTICS_EVENT_ACCEPTED, status=status.HTTP_202_ACCEPTED)


def _host_of(origin: str) -> str:
    """The site's own host, so a referrer from the site itself is not counted as a source."""
    return (urlparse(origin).hostname or "") if origin else ""
