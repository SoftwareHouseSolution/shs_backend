from apps.core.codes import ResponseCode
from apps.core.schema import api_schema, envelope
from apps.core.views import CachedObjectView

from .models import LegalDocument
from .serializers import LegalDocumentSerializer


class LegalDocumentView(CachedObjectView):
    """A published legal page (GET /legal/privacy/). 404 while it is switched off."""

    cache_namespace = "legal"
    success_code = ResponseCode.CONTENT_RETRIEVED

    @api_schema(summary="A legal page (privacy policy)", responses={200: envelope(LegalDocumentSerializer)}, tags=["legal"])
    def get(self, request, **kwargs):
        return super().get(request, **kwargs)

    def build(self, request, slug: str):
        return LegalDocumentSerializer(LegalDocument.objects.get(slug=slug, is_published=True)).data
