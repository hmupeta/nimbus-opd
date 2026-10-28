#!/usr/bin/env python3
"""
fix_nurse_close_permission.py
  - Hides the "Close visit" button from Nurses (Frontend).
  - Enforces Doctor/Admin only on the API (Backend).
  - Adds basic physiological min/max constraints to the Vitals form.
"""
from __future__ import annotations
import re
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

# ─── 1. BACKEND: Restrict the close action ─────────────────────────────
print("==> Patching api/views.py (Backend Permission Lock)")
vp = OPD / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_close = '''    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):'''

new_close = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def close(self, request, pk=None):'''

if old_close in v:
    v = v.replace(old_close, new_close)
    vp.write_text(v, encoding="utf-8")
    print("   patched backend (nurses get 403 Forbidden if they try to close)")
else:
    print("   [WARN] Could not find the 'close' action block in views.py")

# ─── 2. FRONTEND: Hide Button & Add Vitals constraints ─────────────────
print("==> Patching frontend/src/pages/VisitTimeline.tsx")
vt = OPD / "frontend" / "src" / "pages" / "VisitTimeline.tsx"
c = vt.read_text(encoding="utf-8")

# Hide the close button for nurses
old_btn = '''          {t.status !== "closed" && (
            <button onClick={() => closeVisit.mutate()}
              disabled={closeVisit.isPending}
              className="rounded bg-slate-700 text-white text-sm px-3 py-1.5 hover:bg-slate-800 disabled:opacity-50">
              Close visit
            </button>
          )}'''

new_btn = '''          {t.status !== "closed" && (isDoctor || isAdmin) && (
            <button onClick={() => closeVisit.mutate()}
              disabled={closeVisit.isPending}
              className="rounded bg-slate-700 text-white text-sm px-3 py-1.5 hover:bg-slate-800 disabled:opacity-50">
              Close visit
            </button>
          )}'''

if old_btn in c:
    c = c.replace(old_btn, new_btn)
    print("   patched frontend (hid 'Close visit' from nurses)")
else:
    print("   [WARN] Could not find the 'Close visit' button block")

# Add min/max constraints to the Vitals form
old_vitals_form = '''                <label className="text-xs"><span className="text-slate-500">Temp (°C)</span><input type="number" step="0.1" name="temperature_c" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">SpO₂ (%)</span><input type="number" name="spo2" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Systolic</span><input type="number" name="systolic" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Diastolic</span><input type="number" name="diastolic" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Pulse</span><input type="number" name="pulse" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Weight (kg)</span><input type="number" step="0.1" name="weight_kg" className="w-full border rounded px-2 py-1 mt-1" /></label>'''

new_vitals_form = '''                <label className="text-xs"><span className="text-slate-500">Temp (°C)</span><input type="number" step="0.1" min="30" max="45" name="temperature_c" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">SpO₂ (%)</span><input type="number" min="50" max="100" name="spo2" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Systolic</span><input type="number" min="50" max="250" name="systolic" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Diastolic</span><input type="number" min="30" max="150" name="diastolic" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Pulse</span><input type="number" min="30" max="220" name="pulse" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Weight (kg)</span><input type="number" step="0.1" min="1" max="300" name="weight_kg" className="w-full border rounded px-2 py-1 mt-1" /></label>'''

if old_vitals_form in c:
    c = c.replace(old_vitals_form, new_vitals_form)
    print("   added min/max constraints to vitals inputs (preventing 935°C)")
else:
    print("   [WARN] Could not find the vitals form inputs to add constraints")

vt.write_text(c, encoding="utf-8")

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(clinical): restrict visit closing to doctors/admins; add vitals min/max constraints",
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