from django.contrib import admin
from .context import get_current_tenant


class TenantModelAdmin(admin.ModelAdmin):
    """Strictly tenant-scoped ModelAdmin.
    
    Even if is_superuser is True (which grants full Django permissions),
    they will ONLY see data for their own tenant.
    Only is_platform_admin=True bypasses the filter.
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if getattr(request.user, "is_platform_admin", False):
            # Platform admins without a tenant see no clinical data
            if not request.user.tenant:
                return qs.none()
            return qs
            
        tenant = get_current_tenant() or getattr(request.user, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs.none()

    def save_model(self, request, obj, form, change):
        if not getattr(obj, "tenant_id", None):
            tenant = get_current_tenant() or getattr(request.user, "tenant", None)
            if tenant is not None:
                obj.tenant = tenant
        super().save_model(request, obj, form, change)
