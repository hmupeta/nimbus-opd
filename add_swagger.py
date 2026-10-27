#!/usr/bin/env python3
"""
add_swagger.py -- Install and configure drf-spectacular for Swagger UI.
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


# ─── 1. Install drf-spectacular ────────────────────────────────────────
print("==> Installing drf-spectacular")
sh(PY, "-m", "pip", "install", "--quiet", "drf-spectacular>=0.27")

# ─── 2. Patch settings.py ──────────────────────────────────────────────
print("==> Patching config/settings.py")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

if '"drf_spectacular",' not in s:
    s = s.replace(
        '"rest_framework_simplejwt",',
        '"rest_framework_simplejwt",\n    "drf_spectacular",'
    )

if '"DEFAULT_SCHEMA_CLASS"' not in s:
    s = s.replace(
        '"DEFAULT_AUTHENTICATION_CLASSES": [\n        "api.auth.TenantJWTAuthentication",\n    ],',
        '"DEFAULT_AUTHENTICATION_CLASSES": [\n        "api.auth.TenantJWTAuthentication",\n    ],\n    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",'
    )

if "SPECTACULAR_SETTINGS = {" not in s:
    s += '''

SPECTACULAR_SETTINGS = {
    "TITLE": "OPD Multi-Tenant API",
    "DESCRIPTION": "Outpatient Department multi-tenant backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}
'''
sp.write_text(s, encoding="utf-8")
print("   patched config/settings.py")

# ─── 3. Patch urls.py ──────────────────────────────────────────────────
print("==> Patching config/urls.py")
up = ROOT / "config" / "urls.py"
u = up.read_text(encoding="utf-8")

if "SpectacularSwaggerView" not in u:
    if "from drf_spectacular.views import" not in u:
        u = u.replace(
            "urlpatterns = [",
            "from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView\n\nurlpatterns = ["
        )
    if 'path("api/schema/"' not in u:
        u = u.replace(
            'path("api/", include("api.urls")),',
            'path("api/schema/", SpectacularAPIView.as_view(), name="schema"),\n'
            '    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),\n'
            '    path("api/", include("api.urls")),'
        )
    up.write_text(u, encoding="utf-8")
    print("   patched config/urls.py")

# ─── 4. Check ──────────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Start the server and visit:")
print("    http://127.0.0.1:8000/api/docs/")