#!/usr/bin/env python3
"""
fix_staff_roles.py

Adds "Accountant" and "Finance Manager" to the Staff Management role dropdown
and ensures the backend user creation endpoint accepts them.
"""
from __future__ import annotations
import os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def sh(*cmd, cwd=ROOT, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=cwd, check=check)

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

# ═════════════════════════════════════════════════════════════════════
# 1. Patch the Frontend Dropdown
# ═════════════════════════════════════════════════════════════════════
print("==> Patching Frontend Staff/User creation form")
target_file = None
# Search for the file containing "Lab Technician" to find the dropdown
for p in FRONTEND.glob("src/**/*.tsx"):
    txt = p.read_text(encoding="utf-8")
    if "Lab Technician" in txt and ("Receptionist" in txt or "Radiologist" in txt):
        target_file = p
        break

if target_file:
    print(f"   Found dropdown in {target_file.relative_to(FRONTEND)}")
    txt = target_file.read_text(encoding="utf-8")
    
    # Determine if it's an array of strings or objects
    # e.g., ["Doctor", "Nurse"] or [{ value: "Doctor", label: "Doctor" }]
    
    if '"Accountant"' not in txt and "'Accountant'" not in txt:
        # Scenario A: Array of objects { value: "Pharmacist", label: "Pharmacist" }
        if re.search(r'\{\s*value:\s*["\']Pharmacist["\']', txt):
            insert_str = '\n    { value: "Accountant", label: "Accountant" },\n    { value: "Finance Manager", label: "Finance Manager" },'
            # Find Pharmacist and inject after it
            txt = re.sub(
                r'(\{\s*value:\s*["\']Pharmacist["\'],\s*label:\s*["\']Pharmacist["\']\s*\},)',
                r'\1' + insert_str,
                txt, count=1
            )
        # Scenario B: Array of strings ["Pharmacist", "Doctor"]
        elif re.search(r'["\']Pharmacist["\']', txt):
            insert_str = '\n    "Accountant",\n    "Finance Manager",'
            txt = re.sub(
                r'(["\']Pharmacist["\'],?)',
                r'\1' + insert_str,
                txt, count=1
            )
            
        target_file.write_text(txt, encoding="utf-8")
        print("   Added Accountant and Finance Manager to dropdown.")
    else:
        print("   Dropdown already contains the new roles.")
else:
    print("   [WARN] Could not find the frontend file with the role dropdown.")

# ═════════════════════════════════════════════════════════════════════
# 2. Patch the Backend Validation (if it exists)
# ═════════════════════════════════════════════════════════════════════
print("\n==> Checking backend for hardcoded role validation")
backend_patched = False

# Search for any python file in api/ or accounts/ or users/ that has "Lab Technician"
for p in ROOT.glob("**/*.py"):
    if "migrations" in str(p) or "node_modules" in str(p):
        continue
    try:
        txt = p.read_text(encoding="utf-8")
    except Exception:
        continue
    
    if "Lab Technician" in txt and "class" in txt:
        print(f"   Found backend role list in {p.relative_to(ROOT)}")
        if "Accountant" not in txt:
            # Try to inject after Pharmacist or Radiologist
            txt = txt.replace('"Pharmacist"', '"Pharmacist", "Accountant", "Finance Manager"')
            txt = txt.replace("'Pharmacist'", "'Pharmacist', 'Accountant', 'Finance Manager'")
            p.write_text(txt, encoding="utf-8")
            print("   Updated backend role list.")
            backend_patched = True

if not backend_patched:
    print("   No hardcoded backend role list found (or already patched).")

# ═════════════════════════════════════════════════════════════════════
# 3. Build & Deploy
# ═════════════════════════════════════════════════════════════════════
npm = npm_path()
if npm:
    print("\n==> Running Vite build to verify")
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND,
                       capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ build OK")
    else:
        print("   ❌ build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print("     " + line)
        sys.exit(1)

print("\n==> Committing and pushing")
sh("git", "add", ".")
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
if status:
    sh("git", "commit", "-m", "feat(ui): add Accountant and Finance Manager to staff role dropdown")
else:
    print("   (nothing to commit)")
sh("git", "push", "origin", "main")

print("\n✅ Done.")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend  → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")