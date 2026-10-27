#!/usr/bin/env python3
"""
extend_public_tenant.py -- unauthenticated lookup of a tenant's public
                           branding info (name, logo, timezone).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")


# ─── 1. Public view (no auth, no tenant header, no RLS) ────────────────
write("tenants/public_views.py", '''\
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
''')

# ─── 2. Route it in config/urls.py BEFORE api/ ─────────────────────────
print("==> Patching config/urls.py")
up = ROOT / "config" / "urls.py"
u = up.read_text(encoding="utf-8")

if "public_tenant_lookup" not in u:
    # Ensure imports
    if "from tenants.public_views import public_tenant_lookup" not in u:
        u = u.replace(
            "urlpatterns = [",
            "from tenants.public_views import public_tenant_lookup\n\nurlpatterns = [",
        )
    # Add route
    if 'path("api/public/tenant/' not in u:
        u = u.replace(
            'path("api/", include("api.urls")),',
            'path("api/public/tenant/<slug:code>/", public_tenant_lookup, name="public-tenant"),\n    path("api/", include("api.urls")),',
        )
    up.write_text(u, encoding="utf-8")
    print("   patched config/urls.py")

# ─── 3. Confirm ────────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Try:")
print("    Invoke-RestMethod http://127.0.0.1:8000/api/public/tenant/demo/")