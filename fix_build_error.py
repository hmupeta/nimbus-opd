#!/usr/bin/env python3
"""
fix_build_error.py
Diagnoses and attempts to fix the Vite build failure.
"""
import subprocess, sys, shutil
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

npm = npm_path()
if not npm:
    sys.exit("npm not found")

print("==> Running Vite build (capturing output)...")
r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True)

if r.returncode == 0:
    print("   ✓ Build actually succeeded now!")
else:
    print("\n❌ Build failed. Here is the exact error:\n")
    # Print the last 30 lines of output
    output = r.stdout + "\n" + r.stderr
    for line in output.splitlines()[-30:]:
        print("   " + line)
    print("\n--------------------------------------------------")

    # 1. Check for the 'Alert' issue from the earlier interceptor script
    if "Cannot find name 'alert'" in output or "alert is not defined" in output:
        print("==> Fixing 'alert' TypeScript error in client.ts...")
        client_file = FRONTEND / "src" / "api" / "client.ts"
        if client_file.exists():
            txt = client_file.read_text(encoding="utf-8")
            txt = txt.replace("alert(`API Error: ${msg}`);", "window.alert(`API Error: ${msg}`);")
            client_file.write_text(txt, encoding="utf-8")
            print("   Patched window.alert. Re-running build...")
            r2 = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True)
            if r2.returncode == 0:
                print("   ✓ Build succeeded after fix!")
            else:
                print("   ❌ Still failing. Please check the output above.")

    # 2. Check for missing imports (like FileSpreadsheet)
    elif "Cannot find module" in output or "Cannot find name" in output:
        print("==> Missing import detected. Checking FinancialReports.tsx...")
        # Just a generic check, we might need to manually fix it
        print("   Please look at the error above. It is likely a missing import in one of the .tsx files.")

# If build succeeded, commit and push
if r.returncode == 0 or (locals().get('r2') and r2.returncode == 0):
    print("\n==> Committing and pushing...")
    subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if status:
        subprocess.run(["git", "commit", "-m", "fix(ui): add SPA _redirects and fix build errors"], cwd=ROOT, check=True)
    else:
        print("   (nothing to commit)")
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print("\n✅ Pushed successfully.")
    print("Wait for Render to deploy, then refresh /login. It will work.")