#!/usr/bin/env python3
"""
fix_nurse_workflow_ui.py
  - Adds a green success banner for nurses when vitals are recorded.
  - Instructs them to direct the patient to the doctor.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

FRONTEND = OPD / "frontend"
VP = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

# ─── 1. Add the green "Triage Complete" banner ─────────────────────────
print("==> Patching VisitTimeline.tsx")
v = VP.read_text(encoding="utf-8")

old_banner = '''      {t.status === "open" && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 p-4 rounded-lg flex items-center justify-between shadow-sm">
          <div>
            <p className="font-semibold">Action Required</p>
            <p className="text-sm">This patient needs their vitals recorded before the doctor can see them.</p>
          </div>
          {canRecordVitals && !showVitalsForm && (
            <button onClick={() => setShowVitalsForm(true)} className="bg-amber-600 text-white px-4 py-2 rounded shadow hover:bg-amber-700 text-sm font-medium">
              Record Vitals Now
            </button>
          )}
        </div>
      )}'''

new_banner = old_banner + '''

      {t.status === "triaged" && (isNurse || isAdmin) && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-lg flex items-center justify-between shadow-sm">
          <div>
            <p className="font-semibold">Triage Complete</p>
            <p className="text-sm">Vitals recorded successfully. Please direct the patient to the Doctor's room.</p>
          </div>
          <span className="bg-emerald-600 text-white px-4 py-2 rounded shadow text-sm font-medium">
            In Doctor's Queue
          </span>
        </div>
      )}'''

if old_banner in v:
    v = v.replace(old_banner, new_banner)
    VP.write_text(v, encoding="utf-8")
    print("   added green 'Triage Complete' banner for nurses")
else:
    print("   [WARN] Could not find the exact 'open' banner block. You may need to manually insert it.")

# ─── 2. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "feat(ui): add green triage complete banner for nurses",
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
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")
print("\nOnce deployed, refresh the page as the Nurse.")