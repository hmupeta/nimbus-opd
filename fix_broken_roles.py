#!/usr/bin/env python3
"""
fix_broken_roles.py
Reverts the corrupted frontend file and safely adds the new roles.
"""
import subprocess, sys, shutil, os
from pathlib import Path

ROOT = Path.cwd()
FRONTEND = ROOT / "frontend"

# 1. Find the broken file by looking for the syntax error
target_file = None
for p in FRONTEND.glob("src/**/*.tsx"):
    txt = p.read_text(encoding="utf-8")
    if '"Finance Manager", }' in txt or "'Finance Manager', }" in txt:
        target_file = p
        break

if not target_file:
    print("Could not find the broken file. You may need to manually fix the roles array.")
    sys.exit(1)

rel_path = target_file.relative_to(ROOT)
print(f"Reverting {rel_path} to undo the broken injection...")
subprocess.run(["git", "checkout", "--", str(rel_path)], cwd=ROOT, check=True)

# 2. Safely inject the new roles
txt = target_file.read_text(encoding="utf-8")

if "Accountant" in txt:
    print("   File already contains 'Accountant' after revert. Skipping injection.")
else:
    lines = txt.splitlines()
    new_lines = []
    injected = False

    for line in lines:
        new_lines.append(line)
        if "Pharmacist" in line and not injected:
            # Determine if the array uses objects or strings
            if "value:" in line or "label:" in line:
                # It's an object, e.g., { value: "Pharmacist", label: "Pharmacist" },
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f'{indent}{{ value: "Accountant", label: "Accountant" }},')
                new_lines.append(f'{indent}{{ value: "Finance Manager", label: "Finance Manager" }},')
            else:
                # It's a simple string array
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f'{indent}"Accountant",')
                new_lines.append(f'{indent}"Finance Manager",')
            injected = True

    if injected:
        target_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print("   Safely injected Accountant and Finance Manager.")
    else:
        print("   Could not find 'Pharmacist' to inject after. You may need to add them manually.")

# 3. Build & push
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
    subprocess.run(["git", "commit", "-m", "fix(ui): correct role dropdown syntax for new roles"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend  → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")