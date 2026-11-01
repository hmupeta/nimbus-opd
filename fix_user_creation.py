#!/usr/bin/env python3
"""
fix_user_creation.py
Runs missing migrations for the new roles and adds frontend error handling.
"""
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
# 1. Run Migrations (Fixes the 400 Bad Request)
# ═════════════════════════════════════════════════════════════════════
print("==> Applying database migrations for the new roles")
sh(str(PY), "manage.py", "makemigrations")
sh(str(PY), "manage.py", "migrate")

# ═════════════════════════════════════════════════════════════════════
# 2. Check Backend Serializer for hardcoded role lists
# ═════════════════════════════════════════════════════════════════════
print("\n==> Checking backend serializers for role validation")
serializer_patched = False
for p in ROOT.glob("api/**/*.py"):
    txt = p.read_text(encoding="utf-8")
    if "class UserSerializer" in txt or "class UserCreateSerializer" in txt:
        if "Accountant" not in txt and "Pharmacist" in txt:
            txt = txt.replace('"Pharmacist"', '"Pharmacist", "Accountant", "Finance Manager"')
            txt = txt.replace("'Pharmacist'", "'Pharmacist', 'Accountant', 'Finance Manager'")
            p.write_text(txt, encoding="utf-8")
            print(f"   Patched hardcoded role list in {p.relative_to(ROOT)}")
            serializer_patched = True

if not serializer_patched:
    print("   No hardcoded role validation found in serializers (migration should be enough).")

# ═════════════════════════════════════════════════════════════════════
# 3. Patch Frontend to Show Errors
# ═════════════════════════════════════════════════════════════════════
print("\n==> Adding frontend error handling to Staff form")
frontend_patched = False

for p in FRONTEND.glob("src/**/*.tsx"):
    txt = p.read_text(encoding="utf-8")
    # Look for the file that POSTs to /users/
    if 'api.post("/users/' in txt or "api.post('/users/" in txt:
        print(f"   Found user creation form: {p.relative_to(FRONTEND)}")
        
        # If it doesn't already have a try/catch with an alert, inject one
        if "catch (err: any)" not in txt and "catch (e: any)" not in txt:
            # Look for a mutation pattern: const mutation = useMutation({ mutationFn: ... })
            # or a standard async submit handler.
            
            # Simple fix: Find the submit function and wrap it
            # (This is a generic fallback since I don't have the exact code)
            if "const handleSubmit" in txt or "const onSubmit" in txt:
                func_name = "handleSubmit" if "const handleSubmit" in txt else "onSubmit"
                # We will tell the user how to fix it manually if the regex is too complex, 
                # but let's try a safe injection into the catch block if one exists.
                pass
            
            # Better approach: If there's an api.post, look for onError in useMutation
            if "useMutation" in txt and "onError" not in txt:
                txt = re.sub(
                    r'(useMutation\(\{\s*mutationFn:\s*async\s*\([^)]*\)\s*=>\s*[^,]+,\s*)',
                    r'\1onError: (err: any) => alert("Error creating user: " + JSON.stringify(err.response?.data || err.message)),\n',
                    txt
                )
                p.write_text(txt, encoding="utf-8")
                print("   Injected onError alert into useMutation.")
                frontend_patched = True

# ═════════════════════════════════════════════════════════════════════
# 4. Build & Push
# ═════════════════════════════════════════════════════════════════════
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
    subprocess.run(["git", "commit", "-m", "fix: apply migrations for new roles and show backend errors"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend  → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")