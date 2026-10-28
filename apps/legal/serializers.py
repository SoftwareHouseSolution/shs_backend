from rest_framework import serializers

from .models import LegalDocument


class LegalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalDocument
        fields = ["slug", "title", "body", "last_updated", "updated_at"]


class LegalLinkSerializer(serializers.ModelSerializer):
    """A published legal page, as listed in the site data.

    The frontend decides from this list whether a legal page is on — not from the page's
    own endpoint — because this list refreshes like any other content, while a page that
    was cached before it was switched off would keep its last good copy. `in_footer` says
    whether the footer links to it."""

    in_footer = serializers.BooleanField(source="show_in_footer")

    class Meta:
        model = LegalDocument
        fields = ["slug", "title", "in_footer"]


def published_pages():
    return LegalDocument.objects.filter(is_published=True)
