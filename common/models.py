from django.db import models

from .context import get_current_tenant


class TenantManager(models.Manager):
    """Auto-scopes every query to the tenant in context."""

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        return qs.filter(tenant=tenant) if tenant else qs.none()

    def create(self, **kwargs):
        tenant = get_current_tenant()
        if tenant is not None and "tenant" not in kwargs:
            kwargs["tenant"] = tenant
        return super().create(**kwargs)


class TenantAwareModel(models.Model):
    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.PROTECT,
        db_index=True, editable=False,
    )

    objects = TenantManager()
    all_objects = models.Manager()  # escape hatch (admin, scripts)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            tenant = get_current_tenant()
            if tenant is None:
                raise ValueError("No tenant in context and none set on instance")
            self.tenant_id = tenant.pk
        super().save(*args, **kwargs)
