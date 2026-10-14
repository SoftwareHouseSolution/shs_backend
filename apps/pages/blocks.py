"""Content-block strategies.

Each block kind is a small class that knows two things: which fields it requires
(`validate`, used by PageBlock.clean() so the admin shows a field-level error) and what it
looks like on the wire (`serialize`, matching the frontend's StubBlock union exactly).

Adding a kind means writing one class and decorating it with @register — nothing that
renders or validates the existing kinds changes (open/closed). The registry is also the
single list of kinds the API can emit.
"""

from dataclasses import dataclass
from typing import Any, ClassVar

from django.utils.translation import gettext_lazy as _

from apps.content.models import Partner
from apps.content.selectors import active_partners, comparison_table_queryset, published_testimonials
from apps.content.serializers import TestimonialSerializer
from apps.core.media import absolute_media_url
from apps.events.selectors import published_events
from apps.events.serializers import EventSerializer, PhotoSerializer

REQUIRED = _("This field is required for this block type.")


@dataclass
class RenderContext:
    request: Any

    def media(self, file_field) -> str | None:
        return absolute_media_url(file_field, self.request)

    @property
    def serializer_context(self) -> dict:
        return {"request": self.request}


class BlockStrategy:
    kind: ClassVar[str]
    required_fields: ClassVar[tuple[str, ...]] = ()

    def validate(self, block) -> dict[str, list]:
        errors: dict[str, list] = {}
        for name in self.required_fields:
            # Translated text: the default-language column is what must be present.
            value = getattr(block, f"{name}_en", None) if hasattr(block, f"{name}_en") else getattr(block, name)
            if value in (None, ""):
                errors.setdefault(f"{name}_en" if hasattr(block, f"{name}_en") else name, []).append(REQUIRED)
        return errors

    def serialize(self, block, ctx: RenderContext) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError

    @staticmethod
    def optional(value: str) -> str | None:
        return value or None


_REGISTRY: dict[str, BlockStrategy] = {}


def register(cls: type[BlockStrategy]) -> type[BlockStrategy]:
    _REGISTRY[cls.kind] = cls()
    return cls


def strategy_for(kind: str) -> BlockStrategy:
    try:
        return _REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"No block strategy registered for kind {kind!r}") from exc


def registered_kinds() -> list[str]:
    return list(_REGISTRY)


def serialize_block(block, ctx: RenderContext) -> dict:
    return {"kind": block.kind, **strategy_for(block.kind).serialize(block, ctx)}


# ── Strategies ───────────────────────────────────────────────────────────────────────


@register
class IntroBlock(BlockStrategy):
    kind = "intro"
    required_fields = ("heading", "body")

    def serialize(self, block, ctx):
        return {"eyebrow": self.optional(block.eyebrow), "heading": block.heading, "body": block.body}


@register
class CardsBlock(BlockStrategy):
    kind = "cards"

    def serialize(self, block, ctx):
        return {
            "heading": self.optional(block.heading),
            "items": [{"title": i.title, "body": i.body} for i in block.items.all()],
        }


@register
class NumberedBlock(CardsBlock):
    kind = "numbered"


@register
class StepsBlock(BlockStrategy):
    kind = "steps"

    def serialize(self, block, ctx):
        return {
            "heading": self.optional(block.heading),
            "items": [
                {"n": i.number or f"{n:02d}", "title": i.title, "body": i.body}
                for n, i in enumerate(block.items.all(), start=1)
            ],
        }


@register
class HardwareBlock(BlockStrategy):
    kind = "hardware"

    def serialize(self, block, ctx):
        return {
            "heading": self.optional(block.heading),
            "items": [
                {"n": i.number or f"{n:02d}", "title": i.title, "image": ctx.media(i.image)}
                for n, i in enumerate(block.items.all(), start=1)
            ],
        }


@register
class LogosBlock(BlockStrategy):
    kind = "logos"
    required_fields = ("label",)

    def serialize(self, block, ctx):
        partners = active_partners(block.partner_category or Partner.Category.TECHNOLOGY)
        return {
            "label": block.label,
            "logos": [{"src": ctx.media(p.logo), "alt": p.name, "href": p.website or None} for p in partners],
        }


@register
class SpecBlock(BlockStrategy):
    kind = "spec"
    required_fields = ("comparison_table",)

    def serialize(self, block, ctx):
        table = comparison_table_queryset().get(pk=block.comparison_table_id)
        return {"heading": self.optional(block.heading), **table.as_grid()}


@register
class TimelineBlock(BlockStrategy):
    kind = "timeline"

    def serialize(self, block, ctx):
        return {"items": EventSerializer(published_events(), many=True, context=ctx.serializer_context).data}


@register
class GalleryBlock(BlockStrategy):
    kind = "gallery"
    required_fields = ("event",)

    def serialize(self, block, ctx):
        photos = block.event.photos.all() if block.event and block.event.is_published else []
        return {
            "heading": self.optional(block.heading),
            "items": PhotoSerializer(photos, many=True, context=ctx.serializer_context).data,
        }


@register
class TestimonialsBlock(BlockStrategy):
    kind = "testimonials"

    def serialize(self, block, ctx):
        return {
            "heading": self.optional(block.heading),
            "items": TestimonialSerializer(published_testimonials(), many=True, context=ctx.serializer_context).data,
        }


@register
class CtaBlock(BlockStrategy):
    kind = "cta"
    required_fields = ("heading", "body", "label", "url")

    def serialize(self, block, ctx):
        return {"heading": block.heading, "body": block.body, "label": block.label, "href": block.url}
