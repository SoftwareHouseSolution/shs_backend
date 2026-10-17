"""Safe clean-up of media files that no content uses (Admin → System → Media clean-up).

Nothing is deleted outright. A clean-up moves unused files into a trash batch
(MEDIA_TRASH_ROOT, by default MEDIA_ROOT/.trash/<batch>/)
with a manifest, and a batch can be restored or, later, deleted for good. A file counts as
unused only when:

- no FileField/ImageField of any model points at it,
- no text or JSON column mentions it (so a link pasted into content keeps its file), and
- it was last modified more than GRACE ago, so an upload whose record is still being saved
  (the file is written first, the row commits after) is never taken. Re-using a stored
  file for a duplicate upload touches it (apps.core.storage), which restarts that clock.

After moving, references are read again and any file that became used in the meantime is
put straight back.
"""

import json
import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.files import File
from django.db import models
from django.utils import timezone

from . import system_status
from .media import media_files, referenced_media

TRASH_DIR = ".trash"
MANIFEST = "manifest.json"
GRACE = timedelta(hours=1)
_BATCH_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")
_MEDIA_PATH = re.compile(r"[\w./-]+\.\w{2,5}")


@dataclass
class UnusedFile:
    name: str
    size: int


@dataclass
class TrashBatch:
    id: str
    created: object
    user: str
    files: list[dict]

    @property
    def count(self) -> int:
        return len(self.files)

    @property
    def size(self) -> int:
        return sum(f["size"] for f in self.files)


def trash_root() -> Path:
    if settings.MEDIA_TRASH_ROOT:
        return Path(settings.MEDIA_TRASH_ROOT)
    return Path(settings.MEDIA_ROOT) / TRASH_DIR


def protected_names() -> set[str]:
    """Media names the database uses: file fields, plus any path under the media URL that a
    text or JSON column mentions."""
    names = referenced_media()
    media_url = settings.MEDIA_URL.strip("/") + "/"
    from django.apps import apps

    for model in apps.get_models():
        for field in model._meta.concrete_fields:
            if isinstance(field, models.FileField) or not isinstance(field, (models.CharField, models.TextField, models.JSONField)):
                continue
            lookup = {f"{field.attname}__icontains": media_url}
            try:
                values = model._base_manager.filter(**lookup).values_list(field.attname, flat=True)
                for value in values:
                    text = json.dumps(value) if not isinstance(value, str) else value
                    for chunk in text.split(media_url)[1:]:
                        if match := _MEDIA_PATH.match(chunk):
                            names.add(match.group(0))
            except Exception:  # noqa: BLE001 - a column that cannot be searched protects nothing extra
                continue
    return names


def find_unused() -> list[UnusedFile]:
    protected = protected_names()
    cutoff = (timezone.now() - GRACE).timestamp()
    unused = []
    for name, path in media_files():
        stat = path.stat()
        if name not in protected and stat.st_mtime < cutoff:
            unused.append(UnusedFile(name, stat.st_size))
    return sorted(unused, key=lambda f: f.name)


def move_unused_to_trash(user: str) -> TrashBatch | None:
    """Move every currently unused file into a new trash batch. None when there is nothing
    to move."""
    candidates = find_unused()
    if not candidates:
        return None
    root = Path(settings.MEDIA_ROOT)
    batch_id = f"{timezone.localtime():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
    batch_dir = trash_root() / batch_id
    moved = []
    for f in candidates:
        target = batch_dir / f.name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(root / f.name, target)
        except FileNotFoundError:  # removed by someone else meanwhile
            continue
        moved.append({"name": f.name, "size": f.size})

    # Anything that became used while we were moving goes straight back.
    protected = protected_names()
    back = [m for m in moved if m["name"] in protected]
    for m in back:
        shutil.move(batch_dir / m["name"], root / m["name"])
    moved = [m for m in moved if m["name"] not in protected]

    from .models import StoredFile

    StoredFile.objects.filter(name__in=[m["name"] for m in moved]).delete()
    _write_manifest(batch_dir, {"created": timezone.now().isoformat(), "user": user, "files": moved})
    _forget_scans()
    return _read_batch(batch_dir)


def trash_batches() -> list[TrashBatch]:
    root = trash_root()
    if not root.is_dir():
        return []
    batches = [_read_batch(d) for d in root.iterdir() if d.is_dir() and _BATCH_ID.match(d.name)]
    return sorted((b for b in batches if b), key=lambda b: b.id, reverse=True)


def restore(batch_id: str) -> tuple[int, int]:
    """Move a batch's files back. Returns (restored, skipped); a file is skipped when a
    file with its name exists again."""
    batch_dir = _batch_dir(batch_id)
    batch = _read_batch(batch_dir)
    root = Path(settings.MEDIA_ROOT)
    restored = skipped = 0
    from .models import StoredFile
    from .storage import content_digest

    remaining = []
    for f in batch.files:
        source, target = batch_dir / f["name"], root / f["name"]
        if not source.exists() or target.exists():
            skipped += 1
            if source.exists():
                remaining.append(f)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, target)
        restored += 1
        with target.open("rb") as fh:
            digest = content_digest(File(fh))
        StoredFile.objects.get_or_create(sha256=digest, defaults={"name": f["name"], "size": f["size"]})
    if remaining:
        _write_manifest(batch_dir, {"created": batch.created.isoformat(), "user": batch.user, "files": remaining})
    else:
        shutil.rmtree(batch_dir)
    _forget_scans()
    return restored, skipped


def purge(batch_id: str) -> int:
    """Delete a batch for good. Returns how many files it held."""
    batch_dir = _batch_dir(batch_id)
    count = _read_batch(batch_dir).count
    shutil.rmtree(batch_dir)
    return count


def _batch_dir(batch_id: str) -> Path:
    if not _BATCH_ID.match(batch_id or "") or not (trash_root() / batch_id).is_dir():
        raise LookupError(batch_id)
    return trash_root() / batch_id


def _write_manifest(batch_dir: Path, data: dict) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / MANIFEST).write_text(json.dumps(data, indent=1), encoding="utf-8")


def _read_batch(batch_dir: Path) -> TrashBatch | None:
    try:
        data = json.loads((batch_dir / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    from datetime import datetime

    return TrashBatch(batch_dir.name, datetime.fromisoformat(data["created"]), data.get("user", ""), data["files"])


def _forget_scans() -> None:
    cache.delete(system_status.MEDIA_SCAN_KEY)
    for code, _name in settings.LANGUAGES:
        cache.delete(f"{system_status.REPORT_KEY}:{code}")
