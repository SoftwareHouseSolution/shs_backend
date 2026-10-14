"""Abstract building blocks shared by every content model."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        abstract = True


class OrderedModel(models.Model):
    """Manually ordered by `order`, ties broken by id. The admin drags rows to reorder."""

    order = models.PositiveIntegerField(_("order"), default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class PublishableQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class PublishableModel(models.Model):
    """Unpublishing hides a record from the public API without deleting it, so content is
    never lost to a toggle."""

    is_published = models.BooleanField(
        _("published"),
        default=True,
        db_index=True,
        help_text=_("Unpublished items are kept but hidden from the website."),
    )

    objects = PublishableQuerySet.as_manager()

    class Meta:
        abstract = True


class SingletonModel(models.Model):
    """A model with exactly one row (site settings, the home page).

    `save()` pins the primary key and a check constraint enforces it in the database, so a
    second row cannot exist even if something bypasses the admin.
    """

    SINGLETON_PK = 1

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - guarded in the admin too
        raise PermissionError(f"{type(self).__name__} cannot be deleted.")

    @classmethod
    def load(cls):
        obj = cls.objects.filter(pk=cls.SINGLETON_PK).first()
        if obj is None:
            raise cls.DoesNotExist(f"{cls.__name__} has not been configured yet.")
        return obj

    @classmethod
    def singleton_constraint(cls, name: str) -> models.CheckConstraint:
        return models.CheckConstraint(condition=models.Q(pk=cls.SINGLETON_PK), name=name)
