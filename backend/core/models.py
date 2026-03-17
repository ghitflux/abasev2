from django.db import models
from django.utils import timezone

from core.business_reference import resolve_business_reference


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return super().update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class AllObjectsManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    data_referencia_negocio = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = list(update_fields)
            kwargs["update_fields"] = update_fields

        self.data_referencia_negocio = resolve_business_reference(self)
        if update_fields is not None and "data_referencia_negocio" not in update_fields:
            update_fields.append("data_referencia_negocio")
        needs_second_pass = self.pk is None and self.data_referencia_negocio is None

        super().save(*args, **kwargs)

        if needs_second_pass:
            computed = resolve_business_reference(self)
            if computed is not None:
                type(self).all_objects.filter(pk=self.pk).update(
                    data_referencia_negocio=computed
                )
                self.data_referencia_negocio = computed

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def soft_delete(self):
        self.delete()

    def hard_delete(self):
        super().delete()

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])
