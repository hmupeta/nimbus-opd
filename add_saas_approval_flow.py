#!/usr/bin/env python3
"""
add_saas_approval_flow.py -- Require platform admin approval/payment before clinic can log in.
"""
from __future__ import annotations

import os
import re
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

FRONTEND = ROOT / "frontend"

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Block Inactive Tenants from Logging In ────────────────
print("==> Patching api/auth.py")
ap = ROOT / "api" / "auth.py"
a = ap.read_text(encoding="utf-8")

if "def validate(self, attrs):" not in a:
    a = a.replace(
        "from rest_framework_simplejwt.serializers import TokenObtainPairSerializer",
        "from rest_framework_simplejwt.serializers import TokenObtainPairSerializer\nfrom rest_framework import serializers"
    )
    a = a.replace(
        "class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):",
        '''class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # Check if the tenant is active (approved by Platform Admin)
        if self.user.tenant and not self.user.tenant.is_active:
            raise serializers.ValidationError(
                {"detail": "Your clinic is pending approval or payment. Please contact the Platform Administrator."}
            )
        return data
'''
    )
    ap.write_text(a, encoding="utf-8")
    print("   added active tenant check to login")

# ─── 2. BACKEND: Default Tenant to Inactive on Registration ────────────
print("==> Patching api/views.py (TenantRegistrationView)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

if "is_active=False" not in v and "is_active = False" not in v:
    v = v.replace(
        'tenant = Tenant.objects.create(code=clinic_code, name=clinic_name)',
        'tenant = Tenant.objects.create(code=clinic_code, name=clinic_name, is_active=False)'
    )
    vp.write_text(v, encoding="utf-8")
    print("   patched registration to set is_active=False")

# ─── 3. BACKEND: Django Admin Bulk Approve Action ──────────────────────
print("==> Patching tenants/admin.py (Adding Approve Action)")
tp = ROOT / "tenants" / "admin.py"
t = tp.read_text(encoding="utf-8")

if "approve_tenants" not in t:
    action_code = '''
@admin.action(description="Approve selected clinics (Grant Access)")
def approve_tenants(modeladmin, request, queryset):
    queryset.update(is_active=True)

'''
    t = t.replace("@admin.register(Tenant)", action_code + "@admin.register(Tenant)")
    t = t.replace(
        '    list_display = ("code", "name", "city", "country", "is_active", "created_at")',
        '    list_display = ("code", "name", "city", "country", "is_active", "created_at")\n    actions = [approve_tenants]'
    )
    tp.write_text(t, encoding="utf-8")
    print("   added approve_tenants action to admin")

# ─── 4. FRONTEND: Update Registration Success Message ──────────────────
print("==> Patching LandingPage.tsx")
lp = FRONTEND / "src" / "pages" / "LandingPage.tsx"
l = lp.read_text(encoding="utf-8")

old_success = '''              <div className="text-center py-8">
                <div className="text-5xl mb-4">🎉</div>
                <h3 className="text-xl font-bold text-emerald-600 mb-2">Clinic Registered!</h3>
                <p className="text-slate-600 mb-6">Your account is ready. You can now log in and start configuring your clinic.</p>
                <Link to="/login" className="bg-sky-600 text-white px-6 py-2 rounded hover:bg-sky-700 w-full inline-block">Go to Login</Link>
              </div>'''

new_success = '''              <div className="text-center py-8">
                <div className="text-5xl mb-4">⏳</div>
                <h3 className="text-xl font-bold text-amber-600 mb-2">Registration Received</h3>
                <p className="text-slate-600 mb-6 text-sm">
                  Your clinic has been registered. However, your account is currently <b>pending approval and payment</b>. 
                  Our platform team will review your application and contact you shortly.
                </p>
                <Link to="/login" className="bg-slate-200 text-slate-700 px-6 py-2 rounded hover:bg-slate-300 w-full inline-block font-medium">Back to Login</Link>
              </div>'''

if old_success in l:
    l = l.replace(old_success, new_success)
    lp.write_text(l, encoding="utf-8")
    print("   patched LandingPage success message")

print("==> Done. Restart your Django server.")