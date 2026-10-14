"""Versioned content cache with signal-driven invalidation (Observer).

Read endpoints cache their serialised payload per (endpoint, language, query, host). Rather
than track which keys a given edit affects, every key embeds a global *content version*;
any save or delete of a registered content model bumps the version, so the next read of
every endpoint misses and rebuilds. Stale keys simply age out.

That trade — invalidate everything on any edit — is right for a CMS whose content changes
a few times a day and whose reads are cheap to rebuild. It also cannot go wrong: there is
no dependency map to forget to update when a new relationship is added.
"""

import hashlib
import logging
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.utils.translation import get_language

logger = logging.getLogger("apps.core.cache")

VERSION_KEY = "content:version"


def content_version() -> int:
    version = cache.get(VERSION_KEY)
    if version is None:
        version = 1
        cache.add(VERSION_KEY, version, timeout=None)
    return version


def bump_content_version(**_kwargs) -> None:
    try:
        cache.incr(VERSION_KEY)
    except ValueError:
        cache.set(VERSION_KEY, 2, timeout=None)


def _on_content_change(sender, **kwargs):
    # After commit: a reader racing the transaction must not re-cache the old rows under
    # the new version.
    transaction.on_commit(bump_content_version)


def watch_models(*models) -> None:
    """Subscribe the cache to changes on these models. Called from each app's ready()."""
    for model in models:
        uid = f"content-cache-{model._meta.label_lower}"
        post_save.connect(_on_content_change, sender=model, dispatch_uid=f"{uid}-save")
        post_delete.connect(_on_content_change, sender=model, dispatch_uid=f"{uid}-delete")
        for field in model._meta.local_many_to_many:
            m2m_changed.connect(
                _on_content_change, sender=field.remote_field.through, dispatch_uid=f"{uid}-{field.name}"
            )


def cached_payload(namespace: str, request, build: Callable[[], Any], *, timeout: int | None = None) -> Any:
    """Return the cached payload for this request, building and storing it on a miss."""
    query = request.GET.urlencode() if request is not None else ""
    host = request.get_host() if request is not None else ""
    fingerprint = hashlib.sha1(f"{query}|{host}".encode()).hexdigest()[:16]
    key = f"content:{content_version()}:{namespace}:{get_language()}:{fingerprint}"
    payload = cache.get(key)
    if payload is None:
        payload = build()
        cache.set(key, payload, timeout or settings.CONTENT_CACHE_TIMEOUT)
    return payload
