from django.http import HttpResponseForbidden

from .context import (
    db_tenant_context, set_current_ip, set_current_user,
)


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        tenant = getattr(user, "tenant", None) if user and user.is_authenticated else None

        header_tenant = request.headers.get("X-Tenant-ID")
        if header_tenant and (not tenant or str(tenant.id) != header_tenant):
            return HttpResponseForbidden("Tenant mismatch")

        # Set audit context
        set_current_user(user if user and user.is_authenticated else None)
        set_current_ip(request.META.get("REMOTE_ADDR"))

        if tenant is None:
            return self.get_response(request)

        with db_tenant_context(tenant):
            return self.get_response(request)
