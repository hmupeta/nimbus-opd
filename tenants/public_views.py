from django.db import connection
from django.http import Http404, JsonResponse


def public_tenant_lookup(request, code):
    """Unauthenticated endpoint used by a login page to render branding.

    Runs with app.tenant_id cleared, so RLS on tenants_tenant is bypassed
    only for the tenants table itself (which has no tenant_id column),
    and TenantSettings is queried by exact tenant_id.

    We deliberately do NOT expose PII or feature flags — only branding.
    """
    from tenants.models import Tenant, TenantSettings

    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', '', true)")

    tenant = Tenant.objects.filter(code=code, is_active=True).first()
    if tenant is None:
        raise Http404

    # Set the tenant context to this specific tenant so RLS lets us read settings
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant.id)])

    settings_obj = TenantSettings.objects.filter(tenant=tenant).first()

    logo_url = None
    if tenant.logo:
        logo_url = request.build_absolute_uri(tenant.logo.url)

    return JsonResponse({
        "code": tenant.code,
        "name": tenant.name,
        "legal_name": tenant.legal_name,
        "logo_url": logo_url,
        "timezone": settings_obj.timezone if settings_obj else "UTC",
    })
