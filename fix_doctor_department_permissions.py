#!/usr/bin/env python3
"""
fix_doctor_department_permissions.py
  - Hides Lab and Radiology queues from the Doctor's Sidebar.
  - Locks down the Backend ViewSets so Doctors get a 403 Forbidden.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
LP = FRONTEND / "src" / "components" / "Layout.tsx"
VP = ROOT / "api" / "views.py"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT,
                          capture_output=True, text=True)

# ─── 1. FRONTEND: Hide Lab & Radiology from Doctor Sidebar ─────────────
print("==> Updating Layout.tsx (Sidebar permissions)")
l = LP.read_text(encoding="utf-8")

# Remove "doctor" from the roles array for Lab and Radiology
l = l.replace(
    'roles={["lab", "admin", "doctor"]}',
    'roles={["lab", "admin"]}'
)
l = l.replace(
    'roles={["radiology", "admin", "doctor"]}',
    'roles={["radiology", "admin"]}'
)

LP.write_text(l, encoding="utf-8")
print("   hid Lab and Radiology from Doctor sidebar")

# ─── 2. BACKEND: Lock down ViewSets ────────────────────────────────────
print("==> Updating api/views.py (Backend permissions)")
v = VP.read_text(encoding="utf-8")

# Remove "doctor" from LabOrderViewSet
v = v.replace(
    'class LabOrderViewSet(TenantScopedViewSet):\n    serializer_class = LabOrderSerializer\n    queryset = LabOrder.objects.all()\n    permission_classes = [require_roles("admin", "lab", "doctor")]',
    'class LabOrderViewSet(TenantScopedViewSet):\n    serializer_class = LabOrderSerializer\n    queryset = LabOrder.objects.all()\n    permission_classes = [require_roles("admin", "lab")]'
)

# Remove "doctor" from RadiologyOrderViewSet
v = v.replace(
    'class RadiologyOrderViewSet(TenantScopedViewSet):\n    serializer_class = RadiologyOrderSerializer\n    queryset = RadiologyOrder.objects.all()\n    permission_classes = [require_roles("admin", "radiology", "doctor")]',
    'class RadiologyOrderViewSet(TenantScopedViewSet):\n    serializer_class = RadiologyOrderSerializer\n    queryset = RadiologyOrder.objects.all()\n    permission_classes = [require_roles("admin", "radiology")]'
)

VP.write_text(v, encoding="utf-8")
print("   locked down LabOrderViewSet and RadiologyOrderViewSet on backend")

# ─── 3. FRONTEND: Verify build & push ──────────────────────────────────
print("\n==> Running local Vite build to verify")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Local Vite build succeeded!")
    else:
        print("   ❌ Local Vite build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print(f"     {line}")
        sys.exit(1)

# ─── 4. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(rbac): restrict Lab and Radiology queues to their respective departments", check=False)
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")