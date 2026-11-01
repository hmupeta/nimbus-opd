#!/usr/bin/env python3
"""
fix_role_values.py
Fixes the frontend dropdown to send the exact values the backend expects.
"""
import os, subprocess, sys, shutil
from pathlib import Path

ROOT = Path.cwd()
FRONTEND = ROOT / "frontend"

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

# 1. Find and fix the dropdown file
print("==> Searching for the role dropdown file...")
patched = False

for p in FRONTEND.glob("src/**/*.tsx"):
    txt = p.read_text(encoding="utf-8")
    if "Lab Technician" in txt and ("Accountant" in txt or "accountant" in txt):
        print(f"   Found dropdown in {p.relative_to(FRONTEND)}")
        
        # The previous script injected "Accountant" and "Finance Manager".
        # We need to change those to "accountant" and "finance_manager".
        
        # Fix Accountant
        txt = txt.replace('value: "Accountant"', 'value: "accountant"')
        txt = txt.replace("value: 'Accountant'", "value: 'accountant'")
        
        # Fix Finance Manager
        txt = txt.replace('value: "Finance Manager"', 'value: "finance_manager"')
        txt = txt.replace("value: 'Finance Manager'", "value: 'finance_manager'")
        
        p.write_text(txt, encoding="utf-8")
        print("   Updated values to lowercase/underscore to match Django choices.")
        patched = True
        break

if not patched:
    print("   [WARN] Could not find the dropdown file. It may have already been fixed.")

# 2. Build & Push
npm = npm_path()
if npm:
    print("\n==> Running Vite build")
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
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "fix(ui): use lowercase role keys matching Django model"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-frontend → Manual Deploy → Clear build cache & deploy")
print("  (Backend does NOT need to be redeployed, it's already correct)")