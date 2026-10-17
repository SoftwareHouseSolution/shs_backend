"""Admin → System status → Clean up unused files: moves to a trash, restorable."""

import os
import time

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.content.models import Partner
from apps.core import media_cleanup
from apps.core.media import media_files
from apps.core.models import StoredFile
from apps.core.storage import DeduplicatingFileSystemStorage

URL = reverse("admin-media-cleanup")
HOURS_AGO = time.time() - 3 * 3600


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _put(root, name, data=b"x", *, old=True):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if old:
        os.utime(path, (HOURS_AGO, HOURS_AGO))
    return path


@pytest.mark.django_db
def test_only_old_files_no_content_uses_are_moved(media):
    _put(media, "partners/used.svg")
    _put(media, "partners/linked-in-text.svg")
    _put(media, "partners/orphan.svg", b"orphan")
    _put(media, "partners/just-uploaded.svg", old=False)
    Partner.objects.create(name="Used", logo="partners/used.svg", website="https://cms.example.com/media/partners/linked-in-text.svg")

    batch = media_cleanup.move_unused_to_trash("admin")

    assert [f["name"] for f in batch.files] == ["partners/orphan.svg"]
    assert sorted(n for n, _p in media_files()) == ["partners/just-uploaded.svg", "partners/linked-in-text.svg", "partners/used.svg"]
    assert (media / ".trash" / batch.id / "partners" / "orphan.svg").read_bytes() == b"orphan"


@pytest.mark.django_db
def test_nothing_to_move_returns_none(media):
    assert media_cleanup.move_unused_to_trash("admin") is None


@pytest.mark.django_db
def test_a_file_that_becomes_used_while_moving_is_put_back(media, monkeypatch):
    _put(media, "partners/a.svg")
    _put(media, "partners/b.svg", b"b")
    calls = iter([set(), {"partners/a.svg"}])
    monkeypatch.setattr(media_cleanup, "protected_names", lambda: next(calls))

    batch = media_cleanup.move_unused_to_trash("admin")

    assert [f["name"] for f in batch.files] == ["partners/b.svg"]
    assert (media / "partners" / "a.svg").exists()


@pytest.mark.django_db
def test_restore_puts_files_back_and_reindexes_them(media):
    _put(media, "clients/gone.webp", b"logo")
    batch = media_cleanup.move_unused_to_trash("admin")
    assert not StoredFile.objects.filter(name="clients/gone.webp").exists()

    assert media_cleanup.restore(batch.id) == (1, 0)
    assert (media / "clients" / "gone.webp").read_bytes() == b"logo"
    assert StoredFile.objects.filter(name="clients/gone.webp").exists()
    assert media_cleanup.trash_batches() == []


@pytest.mark.django_db
def test_restore_skips_a_name_that_exists_again(media):
    _put(media, "clients/a.webp", b"old")
    batch = media_cleanup.move_unused_to_trash("admin")
    _put(media, "clients/a.webp", b"new")

    assert media_cleanup.restore(batch.id) == (0, 1)
    assert (media / "clients" / "a.webp").read_bytes() == b"new"
    assert media_cleanup.trash_batches()[0].count == 1


@pytest.mark.django_db
def test_purge_deletes_the_batch_for_good(media):
    _put(media, "clients/a.webp")
    batch = media_cleanup.move_unused_to_trash("admin")
    assert media_cleanup.purge(batch.id) == 1
    assert not (media / ".trash" / batch.id).exists()


@pytest.mark.parametrize("batch_id", ["", "../clients", "20260101-000000-zzzzzz", "20260101-000000-abcdef"])
def test_unknown_or_unsafe_batch_ids_are_refused(media, batch_id):
    with pytest.raises(LookupError):
        media_cleanup.purge(batch_id)


def test_the_trash_is_not_counted_as_media(media):
    _put(media, ".trash/20260101-000000-abcdef/clients/a.webp")
    _put(media, "clients/b.webp")
    assert [n for n, _p in media_files()] == ["clients/b.webp"]


@pytest.mark.django_db
def test_reusing_a_stored_file_restarts_its_grace_period(media):
    storage = DeduplicatingFileSystemStorage(location=media)
    name = storage.save("clients/a.webp", ContentFile(b"same"))
    os.utime(media / name, (HOURS_AGO, HOURS_AGO))
    storage.save("clients/b.webp", ContentFile(b"same"))
    assert (media / name).stat().st_mtime > time.time() - 60


@pytest.mark.django_db
def test_the_page_previews_then_cleans_restores_and_purges(admin_client, media):
    _put(media, "clients/orphan.webp")

    page = admin_client.get(URL)
    assert page.status_code == 200 and page.context["unused_count"] == 1
    assert (media / "clients" / "orphan.webp").exists()  # GET changes nothing

    admin_client.post(URL, {"action": "clean"})
    batch = media_cleanup.trash_batches()[0]
    assert not (media / "clients" / "orphan.webp").exists()

    admin_client.post(URL, {"action": "restore", "batch": batch.id})
    assert (media / "clients" / "orphan.webp").exists()

    admin_client.post(URL, {"action": "clean"})
    response = admin_client.post(URL, {"action": "purge", "batch": media_cleanup.trash_batches()[0].id}, follow=True)
    assert media_cleanup.trash_batches() == []
    assert response.status_code == 200


@pytest.mark.django_db
def test_the_status_page_links_to_the_clean_up(admin_client):
    assert URL.encode() in admin_client.get(reverse("admin-system-status")).content


@pytest.mark.django_db
def test_editors_cannot_clean_up(client, django_user_model, media):
    _put(media, "clients/orphan.webp")
    client.force_login(django_user_model.objects.create_user("editor", password="x", is_staff=True))
    assert client.post(URL, {"action": "clean"}).status_code == 403
    assert (media / "clients" / "orphan.webp").exists()
