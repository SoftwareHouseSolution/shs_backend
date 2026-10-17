"""Media storage that never keeps the same file twice."""

import hashlib
import os

from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError, transaction


def content_digest(content) -> str:
    """SHA-256 of a Django File (an upload, or a file opened from disk), read in chunks so
    a 60 MB video is never held in memory. Leaves the file rewound for the next reader."""
    digest = hashlib.sha256()
    for chunk in content.chunks():
        digest.update(chunk)
    content.seek(0)
    return digest.hexdigest()


class DeduplicatingFileSystemStorage(FileSystemStorage):
    """FileSystemStorage that returns the name of an already-stored identical file instead
    of writing a second copy.

    Uploading the same image or video again — to the same record or any other — reuses the
    first file and its URL; the media folder gains nothing. The index is
    apps.core.models.StoredFile; a file deleted from disk behind its back is simply written
    again on the next upload.

    Several records may therefore share one file. That is safe because nothing in this
    project deletes media when a record changes or is deleted; anything added later that
    does (django-cleanup, a pre_delete signal) must first check no other record uses it.
    """

    def save(self, name, content, max_length=None):
        if name is None:
            name = content.name
        if not hasattr(content, "chunks"):
            from django.core.files import File

            content = File(content, name)

        from .models import StoredFile

        digest = content_digest(content)
        existing = StoredFile.objects.filter(sha256=digest).values_list("name", flat=True).first()
        if existing and self.exists(existing) and (max_length is None or len(existing) <= max_length):
            try:
                # Fresh again: the media clean-up never takes files touched in the last hour,
                # which covers the moment before this upload's record is saved.
                os.utime(self.path(existing))
            except OSError:
                pass
            return existing

        name = super().save(name, content, max_length=max_length)
        try:
            # A savepoint, so losing a race with an identical concurrent upload does not
            # break the admin's surrounding transaction; that upload's row wins.
            with transaction.atomic():
                StoredFile.objects.update_or_create(sha256=digest, defaults={"name": name, "size": content.size})
        except IntegrityError:
            pass
        return name
