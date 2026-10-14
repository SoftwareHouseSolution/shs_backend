from apps.core.schema import api_schema, envelope
from apps.core.views import CachedObjectView

from . import selectors
from .serializers import (
    BadgeSerializer,
    FooterColumnSerializer,
    LanguageSerializer,
    NavEntrySerializer,
    SitePayloadSerializer,
    SiteSettingsSerializer,
    SocialLinkSerializer,
)


class SiteView(CachedObjectView):
    """Everything every page needs, in one request: settings, navigation, footer, social
    links and badges. The frontend layout fetches this once per language."""

    cache_namespace = "site"

    @api_schema(
        summary="Site-wide settings, navigation and footer",
        responses={200: envelope(SitePayloadSerializer)},
        tags=["site"],
    )
    def get(self, request, **kwargs):
        return super().get(request, **kwargs)

    def build(self, request, **kwargs):
        ctx = {"request": request}
        nav = [entry for entry in selectors.navigation_tree() if entry.url or entry.active_children]
        return {
            "language": LanguageSerializer.current(),
            "settings": SiteSettingsSerializer(selectors.get_site_settings(), context=ctx).data,
            "navigation": NavEntrySerializer(nav, many=True, context=ctx).data,
            "footer_columns": FooterColumnSerializer(selectors.footer_columns(), many=True).data,
            "social_links": SocialLinkSerializer(selectors.social_links(), many=True).data,
            "badges": BadgeSerializer(selectors.badges(), many=True, context=ctx).data,
        }
