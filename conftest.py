"""Shared pytest fixtures.

The test database is PostgreSQL (config.settings.test), migrated once and loaded with the
real seed content once per session, so API tests exercise the same 16 pages, 367 clients
and bilingual copy the site ships with. Each test runs in a rolled-back transaction.
"""

import json
from pathlib import Path

import pytest
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient

SEED_FILE = Path(settings.BASE_DIR) / "seed" / "content.json"
SEED_MEDIA = Path(settings.BASE_DIR) / "seed" / "media"


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    from apps.core.seeding import ContentSeeder
    from apps.site_config.models import SiteSettings

    with django_db_blocker.unblock():
        if not SiteSettings.objects.exists():
            data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
            ContentSeeder(data, SEED_MEDIA, log=lambda *_: None).run()


@pytest.fixture(autouse=True)
def _isolated_cache():
    # Rolled-back transactions never fire on_commit, so the content version would not move
    # between tests; clearing keeps one test's cached payload out of the next.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def superuser(db, django_user_model):
    return django_user_model.objects.create_superuser("admin-test", "admin@example.com", "x" * 12)


@pytest.fixture
def admin_client(client, superuser):
    client.force_login(superuser)
    return client
