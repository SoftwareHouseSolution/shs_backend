"""Uploading a file that is already stored reuses it instead of writing a copy."""

import io

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command

from apps.content.models import Partner
from apps.core.models import StoredFile
from apps.core.storage import DeduplicatingFileSystemStorage, content_digest

SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h1v1z"/></svg>'


@pytest.fixture
def storage(tmp_path):
    return DeduplicatingFileSystemStorage(location=tmp_path)


def _files(tmp_path):
    return sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())


def test_the_default_storage_deduplicates():
    assert isinstance(default_storage, DeduplicatingFileSystemStorage)


@pytest.mark.django_db
def test_identical_content_is_stored_once(storage, tmp_path):
    first = storage.save("clients/logo-aaaa1111.png", ContentFile(b"same bytes"))
    second = storage.save("partners/other-name-bbbb2222.png", ContentFile(b"same bytes"))
    assert second == first
    assert _files(tmp_path) == [first]
    assert StoredFile.objects.filter(name=first, size=10).count() == 1


@pytest.mark.django_db
def test_different_content_gets_its_own_file(storage, tmp_path):
    a = storage.save("clients/a.png", ContentFile(b"one"))
    b = storage.save("clients/b.png", ContentFile(b"two"))
    assert a != b and len(_files(tmp_path)) == 2


@pytest.mark.django_db
def test_a_file_removed_from_disk_is_written_again(storage, tmp_path):
    name = storage.save("clients/a.png", ContentFile(b"bytes"))
    (tmp_path / name).unlink()
    again = storage.save("clients/a-again.png", ContentFile(b"bytes"))
    assert (tmp_path / again).exists()
    assert StoredFile.objects.get(sha256=content_digest(ContentFile(b"bytes"))).name == again


@pytest.mark.django_db
def test_a_stored_name_too_long_for_the_field_is_not_reused(storage):
    long = storage.save(f"clients/{'x' * 80}.png", ContentFile(b"bytes"))
    short = storage.save("c/y.png", ContentFile(b"bytes"), max_length=20)
    assert short != long and len(short) <= 20


@pytest.mark.django_db
def test_two_records_uploading_the_same_logo_share_one_file():
    a = Partner.objects.create(name="A", logo=ContentFile(SVG, name="Logo A.svg"))
    b = Partner.objects.create(name="B", logo=ContentFile(SVG, name="Logo B.svg"))
    assert a.logo.name == b.logo.name
    assert b.logo.url == a.logo.url


@pytest.mark.django_db
def test_index_media_prefers_the_copy_content_uses(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "partners").mkdir()
    (tmp_path / "partners" / "unused-copy.svg").write_bytes(SVG)
    (tmp_path / "partners" / "used.svg").write_bytes(SVG)
    (tmp_path / "partners" / "other.svg").write_bytes(SVG + b" ")
    Partner.objects.create(name="Used", logo="partners/used.svg")

    call_command("index_media", stdout=io.StringIO())

    assert StoredFile.objects.count() == 2
    assert StoredFile.objects.filter(name="partners/used.svg").exists()


@pytest.mark.django_db
def test_index_media_if_empty_runs_only_once(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "a.svg").write_bytes(SVG)
    call_command("index_media", "--if-empty", stdout=io.StringIO())
    assert StoredFile.objects.count() == 1

    (tmp_path / "b.svg").write_bytes(SVG + b" ")
    out = io.StringIO()
    call_command("index_media", "--if-empty", stdout=out)
    assert StoredFile.objects.count() == 1 and "skipping" in out.getvalue()
