#!/usr/bin/env python3
"""
fix_radiology_dashboard.py -- Redirect radiologists to their queue and fix patient permissions.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
if not FRONTEND.exists():
    sys.exit(f"Frontend not found at {FRONTEND}.")

# ─── 1. BACKEND: Allow Radiology to view Patients ──────────────────────
print("==> Patching api/views.py (PatientViewSet permissions)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_perms = '''permission_classes = [require_roles(
        "admin", "receptionist", "doctor", "nurse", "pharmacist", "lab")]'''
new_perms = '''permission_classes = [require_roles(
        "admin", "receptionist", "doctor", "nurse", "pharmacist", "lab", "radiology")]'''

if old_perms in v:
    v = v.replace(old_perms, new_perms)
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py")
else:
    print("   [WARN] PatientViewSet permissions string not found.")

# ─── 2. FRONTEND: Redirect Radiology role in Dashboard ─────────────────
print("==> Updating src/pages/Dashboard.tsx")
dp = FRONTEND / "src" / "pages" / "Dashboard.tsx"
d = dp.read_text(encoding="utf-8")

# Add the redirect logic
if 'user?.role === "radiology"' not in d:
    # Find the block where other roles are checked
    target = '''  if (user?.role === "receptionist") {
    return <Navigate to="/billing" replace />;
  }'''
    
    replacement = '''  if (user?.role === "receptionist") {
    return <Navigate to="/billing" replace />;
  }
  if (user?.role === "radiology") {
    return <Navigate to="/radiology" replace />;
  }'''
    
    if target in d:
        d = d.replace(target, replacement)
        dp.write_text(d, encoding="utf-8")
        print("   patched Dashboard.tsx")
    else:
        print("   [WARN] Could not find receptionist redirect block to insert radiology redirect.")

print("==> Done. Restart the Django server and refresh your browser.")