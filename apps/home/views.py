from apps.core.schema import ERROR_404, api_schema, envelope
from apps.core.views import CachedObjectView

from .composer import build_home_payload
from .serializers import HomePayloadSerializer


class HomeView(CachedObjectView):
    cache_namespace = "home"

    @api_schema(
        summary="Home page content",
        responses={200: envelope(HomePayloadSerializer), 404: ERROR_404},
        tags=["pages"],
    )
    def get(self, request, **kwargs):
        return super().get(request, **kwargs)

    def build(self, request, **kwargs):
        return build_home_payload(request)
