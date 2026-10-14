"""Upload naming and public media URLs."""

import uuid
from pathlib import Path
from urllib.parse import urljoin

from django.conf import settings
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify

from .validators import validate_site_link


@deconstructible
class UploadTo:
    """`<prefix>/<slugified-name>-<8 hex>.<ext>` — readable in the media folder, and never
    overwrites an earlier upload with the same name (replacing a file in the admin then
    busts every cache that held the old URL)."""

    def __init__(self, prefix: str):
        self.prefix = prefix.strip("/")

    def __call__(self, instance, filename: str) -> str:
        path = Path(filename)
        stem = slugify(path.stem)[:60] or "file"
        return f"{self.prefix}/{stem}-{uuid.uuid4().hex[:8]}{path.suffix.lower()}"

    def __eq__(self, other):
        return isinstance(other, UploadTo) and other.prefix == self.prefix


def absolute_media_url(file_field, request=None) -> str | None:
    """Public URL for a stored file, or None when the field is empty.

    MEDIA_PUBLIC_BASE_URL wins when set (production behind a proxy or CDN); otherwise the
    URL is made absolute from the request, which is what the Next.js server and the browser
    both need — a bare /media/… path would resolve against the frontend's own origin.
    """
    if not file_field:
        return None
    url = file_field.url
    base = settings.MEDIA_PUBLIC_BASE_URL
    if base:
        return urljoin(base.rstrip("/") + "/", url.lstrip("/"))
    if request is not None:
        return request.build_absolute_uri(url)
    return url


class LinkField(models.CharField):
    """A CharField that only accepts site links (see validate_site_link)."""

    default_validators = [validate_site_link]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 500)
        super().__init__(*args, **kwargs)
