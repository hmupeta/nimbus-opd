#!/usr/bin/env python3
from pathlib import Path

ROOT = Path.cwd()
pv = ROOT / "tenants" / "public_views.py"
code = pv.read_text(encoding="utf-8")

old_code = '''    tenant = Tenant.objects.filter(code=code, is_active=True).first()
    if tenant is None:
        raise Http404

    settings_obj = TenantSettings.objects.filter(tenant=tenant).first()'''

new_code = '''    tenant = Tenant.objects.filter(code=code, is_active=True).first()
    if tenant is None:
        raise Http404

    # Set the tenant context to this specific tenant so RLS lets us read settings
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant.id)])

    settings_obj = TenantSettings.objects.filter(tenant=tenant).first()'''

if old_code in code:
    code = code.replace(old_code, new_code)
    pv.write_text(code, encoding="utf-8")
    print("   patched tenants/public_views.py")
else:
    print("   already patched or structure changed")