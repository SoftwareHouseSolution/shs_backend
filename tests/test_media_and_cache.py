import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.core.cache import bump_content_version
from apps.core.media import UploadTo, absolute_media_url
from apps.core.validators import MaxFileSizeValidator, SafeImageValidator
from apps.pages.models import Page


def _png(size=(4, 4)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, "PNG")
    return buf.getvalue()


def test_real_images_pass():
    SafeImageValidator()(SimpleUploadedFile("ok.png", _png()))


def test_a_renamed_non_image_is_rejected():
    with pytest.raises(ValidationError) as exc:
        SafeImageValidator()(SimpleUploadedFile("evil.png", b"MZ\x90\x00 not a png"))
    assert exc.value.code == "invalid_image"


@pytest.mark.parametrize(
    "svg",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:alert(1)"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
    ],
)
def test_active_svg_content_is_rejected(svg):
    with pytest.raises(ValidationError) as exc:
        SafeImageValidator()(SimpleUploadedFile("logo.svg", svg))
    assert exc.value.code == "unsafe_svg"


def test_plain_svg_passes():
    SafeImageValidator()(SimpleUploadedFile("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h1v1z"/></svg>'))


def test_size_limit_follows_settings(settings):
    settings.MAX_IMAGE_UPLOAD_MB = 1
    big = SimpleUploadedFile("big.png", b"0" * (1024 * 1024 + 1))
    with pytest.raises(ValidationError) as exc:
        MaxFileSizeValidator("MAX_IMAGE_UPLOAD_MB")(big)
    assert exc.value.code == "file_too_large"


def test_upload_names_are_readable_and_unique():
    a = UploadTo("hero")(None, "My Slide (Final).JPG")
    b = UploadTo("hero")(None, "My Slide (Final).JPG")
    assert a.startswith("hero/my-slide-final-") and a.endswith(".jpg") and a != b


@pytest.mark.django_db
def test_media_urls_use_the_public_base_when_configured(settings, api):
    settings.MEDIA_PUBLIC_BASE_URL = "https://cdn.example.com"
    page = Page.objects.get(slug="about-company")
    assert absolute_media_url(page.header_image).startswith("https://cdn.example.com/media/pages/")
    data = api.get("/api/v1/pages/about-company/").json()["data"]
    assert data["header_image"].startswith("https://cdn.example.com/media/")


@pytest.mark.django_db
def test_media_urls_are_absolute_from_the_request_by_default(api):
    data = api.get("/api/v1/pages/about-company/").json()["data"]
    assert data["header_image"].startswith("http://testserver/media/pages/")


@pytest.mark.django_db
def test_media_is_served_in_the_test_storage(api):
    url = api.get("/api/v1/pages/about-company/").json()["data"]["header_image"]
    page = Page.objects.get(slug="about-company")
    assert page.header_image.storage.exists(page.header_image.name)
    assert url.endswith(page.header_image.name)


@pytest.mark.django_db
def test_responses_are_cached_until_content_changes(api, django_capture_on_commit_callbacks):
    first = api.get("/api/v1/pages/about-company/").json()["data"]["title"]
    Page.objects.filter(slug="about-company").update(title_en="Changed")  # no signal
    assert api.get("/api/v1/pages/about-company/").json()["data"]["title"] == first  # still cached

    with django_capture_on_commit_callbacks(execute=True):
        page = Page.objects.get(slug="about-company")
        page.title_en = "Changed again"
        page.save()  # post_save → version bump after commit
    assert api.get("/api/v1/pages/about-company/").json()["data"]["title"] == "Changed again"


@pytest.mark.django_db
def test_cache_is_per_language(api):
    bump_content_version()
    en = api.get("/api/v1/pages/about-company/", {"lang": "en"}).json()["data"]["title"]
    ar = api.get("/api/v1/pages/about-company/", {"lang": "ar"}).json()["data"]["title"]
    assert (en, ar) == ("About Company", "عن الشركة")
