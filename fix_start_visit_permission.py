#!/usr/bin/env python3
"""
fix_start_visit_permission.py
  - Backend: Enforces that only "admin" or "receptionist" can POST to /api/visits/
  - Frontend: Hides the "Start visit" button on the Patients page for other roles.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

# ─── 1. BACKEND: Lock down visit creation ──────────────────────────────
print("==> Patching api/views.py (Backend Permission Lock)")
vp = OPD / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Insert the create() override into VisitViewSet
if "def create(self, request, *args, **kwargs):" not in v.split("class VisitViewSet")[1].split("class ")[0]:
    # Find the VisitViewSet class and insert right after its permission_classes
    marker = 'class VisitViewSet(TenantScopedViewSet):'
    
    new_create_logic = '''
    def create(self, request, *args, **kwargs):
        if request.user.role not in ["admin", "receptionist"]:
            return Response(
                {"detail": "Only a Receptionist or Admin can start a new visit."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)
'''
    
    # Insert it safely after the permission classes
    v = v.replace(
        'permission_classes = [require_roles(\n        "admin", "receptionist", "doctor", "nurse")]',
        'permission_classes = [require_roles(\n        "admin", "receptionist", "doctor", "nurse")]\n' + new_create_logic
    )
    
    # Fallback string match just in case formatting is different
    if new_create_logic not in v:
        v = v.replace(
            'class VisitViewSet(TenantScopedViewSet):',
            'class VisitViewSet(TenantScopedViewSet):\n' + new_create_logic
        )
        
    vp.write_text(v, encoding="utf-8")
    print("   patched backend (VisitViewSet.create restricted to admin/receptionist)")
else:
    print("   backend already locked")

# ─── 2. FRONTEND: Hide "Start Visit" button ────────────────────────────
print("==> Patching frontend/src/pages/Patients.tsx")
pp = OPD / "frontend" / "src" / "pages" / "Patients.tsx"
p = pp.read_text(encoding="utf-8")

# Ensure currentUser is imported
if "import { currentUser }" not in p:
    p = p.replace(
        'import { api } from "../api/client";',
        'import { api } from "../api/client";\nimport { currentUser } from "../api/auth";'
    )
    # Add user variable inside the component
    p = p.replace(
        'export default function Patients() {',
        'export default function Patients() {\n  const user = currentUser();\n  const canStartVisit = user?.role === "receptionist" || user?.role === "admin";'
    )

# Wrap the Start Visit button in a conditional
old_btn = '''                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => startVisit.mutate(p.id)}
                      disabled={startVisit.isPending}
                      className="rounded bg-emerald-600 text-white text-xs px-3 py-1.5 hover:bg-emerald-700 disabled:opacity-50"
                    >
                      Start visit
                    </button>
                  </td>'''

new_btn = '''                  <td className="px-4 py-3 text-right">
                    {canStartVisit && (
                      <button
                        onClick={() => startVisit.mutate(p.id)}
                        disabled={startVisit.isPending}
                        className="rounded bg-emerald-600 text-white text-xs px-3 py-1.5 hover:bg-emerald-700 disabled:opacity-50"
                      >
                        Start visit
                      </button>
                    )}
                  </td>'''

if old_btn in p:
    p = p.replace(old_btn, new_btn)
    pp.write_text(p, encoding="utf-8")
    print("   patched frontend (hid 'Start visit' for non-receptionists)")
else:
    print("   [WARN] Could not find exact 'Start visit' button block in Patients.tsx")

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(visits): restrict starting visits to receptionists and admins only",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")