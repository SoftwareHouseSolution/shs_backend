"""Upload and link validation shared by every model with a file or a URL field."""

import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif"]
LOGO_EXTENSIONS = [*IMAGE_EXTENSIONS, "svg"]
ICON_EXTENSIONS = ["png", "svg", "ico"]
VIDEO_EXTENSIONS = ["mp4", "webm"]


@deconstructible
class MaxFileSizeValidator:
    """Rejects files over `setting_name` megabytes. The limit is read at validation time so
    it follows the environment without a migration."""

    def __init__(self, setting_name: str):
        self.setting_name = setting_name

    def __call__(self, file):
        limit_mb = getattr(settings, self.setting_name)
        if file.size > limit_mb * 1024 * 1024:
            raise ValidationError(
                _("File is too large (%(size).1f MB). The limit is %(limit)d MB."),
                code="file_too_large",
                params={"size": file.size / (1024 * 1024), "limit": limit_mb},
            )

    def __eq__(self, other):
        return isinstance(other, MaxFileSizeValidator) and other.setting_name == self.setting_name


# Anything executable inside an SVG. Uploaded SVGs are served from the media origin, so a
# script in one would run with that origin's privileges if opened directly.
_SVG_DANGER = re.compile(
    rb"<\s*script|<\s*foreignObject|\son[a-z]+\s*=|javascript:|<\s*iframe|<\s*embed|<\s*object",
    re.IGNORECASE,
)


@deconstructible
class SafeImageValidator:
    """Verifies raster images really decode, and that SVGs carry no active content."""

    def __call__(self, file):
        ext = Path(file.name).suffix.lower().lstrip(".")
        pos = file.tell() if hasattr(file, "tell") else 0
        try:
            if ext == "svg":
                head = file.read()
                if b"<svg" not in head[:4096].lower() and b"<svg" not in head.lower():
                    raise ValidationError(_("This file is not a valid SVG image."), code="invalid_svg")
                if _SVG_DANGER.search(head):
                    raise ValidationError(
                        _("SVG files may not contain scripts, event handlers or embedded content."),
                        code="unsafe_svg",
                    )
            elif ext == "ico":
                return
            else:
                from PIL import Image, UnidentifiedImageError

                try:
                    with Image.open(file) as img:
                        img.verify()
                except (UnidentifiedImageError, OSError, SyntaxError) as exc:
                    raise ValidationError(
                        _("Upload a valid image. The file is not an image or is corrupted."),
                        code="invalid_image",
                    ) from exc
        finally:
            if hasattr(file, "seek"):
                file.seek(pos)

    def __eq__(self, other):
        return isinstance(other, SafeImageValidator)


image_validators = [
    FileExtensionValidator(IMAGE_EXTENSIONS),
    MaxFileSizeValidator("MAX_IMAGE_UPLOAD_MB"),
    SafeImageValidator(),
]
logo_validators = [
    FileExtensionValidator(LOGO_EXTENSIONS),
    MaxFileSizeValidator("MAX_IMAGE_UPLOAD_MB"),
    SafeImageValidator(),
]
icon_validators = [
    FileExtensionValidator(ICON_EXTENSIONS),
    MaxFileSizeValidator("MAX_IMAGE_UPLOAD_MB"),
    SafeImageValidator(),
]
video_validators = [
    FileExtensionValidator(VIDEO_EXTENSIONS),
    MaxFileSizeValidator("MAX_VIDEO_UPLOAD_MB"),
]


# ── Links ────────────────────────────────────────────────────────────────────────────
# A site link is one of: an internal path ("/customers", "/#contact"), a same-page
# fragment ("#contact"), an absolute http(s) URL, or a mailto:/tel: link. Internal paths are
# stored WITHOUT the /en or /ar prefix; the frontend adds the reader's language.
_LINK = re.compile(
    r"^(/[A-Za-z0-9\-._~/]*(#[A-Za-z0-9\-_]+)?|#[A-Za-z0-9\-_]+|https?://\S+|mailto:\S+@\S+|tel:\+?[0-9]+)$"
)
_LOCALE_PREFIX = re.compile(r"^/(en|ar)(/|$)")


def validate_site_link(value: str):
    if not _LINK.match(value):
        raise ValidationError(
            _(
                "Enter an internal path (/about-company), a fragment (#contact), "
                "a full URL (https://…), or a mailto:/tel: link."
            ),
            code="invalid_link",
        )
    if _LOCALE_PREFIX.match(value):
        raise ValidationError(
            _("Do not include /en or /ar — the website adds the reader's language itself."),
            code="localized_link",
        )
