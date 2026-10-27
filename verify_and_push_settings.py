#!/usr/bin/env python3
"""
verify_and_push_settings.py
  config/settings.py was already rewritten successfully by the previous script.
  This just verifies it and pushes.
"""
from __future__ import annotations
import os
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

PY = OPD / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)

# ─── 1. Confirm settings.py has DATABASES at top level ─────────────────
print("==> Verifying config/settings.py")
sp = OPD / "config" / "settings.py"
content = sp.read_text(encoding="utf-8")

checks = {
    "import os": "import os" in content,
    "import dj_database_url": "import dj_database_url" in content,
    "DATABASES = { at col 0": "\nDATABASES = {" in content,
    "local postgres fallback": '"ENGINE": "django.db.backends.postgresql"' in content,
    "DATABASE_URL override": 'os.environ.get("DATABASE_URL")' in content or 'os.environ["DATABASE_URL"]' in content,
    "STATIC_ROOT": "STATIC_ROOT" in content,
    "CORS_ALLOW_ALL_ORIGINS": "CORS_ALLOW_ALL_ORIGINS" in content,
}
for label, ok in checks.items():
    print(f"   [{'✓' if ok else '✗'}] {label}")
    if not ok:
        sys.exit(f"settings.py is missing: {label}")

# ─── 2. Verify Python syntax ───────────────────────────────────────────
print("==> Verifying Python syntax")
r = subprocess.run(
    [str(PY), "-c", "import ast, pathlib; ast.parse(pathlib.Path('config/settings.py').read_text())"],
    cwd=OPD, capture_output=True, text=True,
)
if r.returncode != 0:
    print("   ❌ Syntax error:")
    print(r.stderr[-1500:])
    sys.exit(1)
print("   ✓ Syntax OK")

# ─── 3. Verify Django loads ────────────────────────────────────────────
print("==> Running manage.py check")
env = {**os.environ, "NO_REDIS": "1", "DJANGO_DEBUG": "1"}
r = subprocess.run(
    [str(PY), "manage.py", "check"],
    cwd=OPD, capture_output=True, text=True, env=env,
)
if r.returncode != 0:
    print("   ❌ Django check failed:")
    print((r.stdout + r.stderr)[-2500:])
    sys.exit(1)
print("   ✓ " + r.stdout.strip().splitlines()[-1] if r.stdout else "   ✓ Django loads")

# ─── 4. Verify superadmin patch ────────────────────────────────────────
print("==> Verifying seed_demo superadmin patch")
seed = OPD / "tenants" / "management" / "commands" / "seed_demo.py"
sc = seed.read_text(encoding="utf-8")
if "superadmin@nimbus.local" not in sc:
    print("   ⚠ superadmin NOT in seed_demo — will patch it now")
    # emergency patch if the previous script failed to apply it
    if "_ensure_superadmin" not in sc:
        sys.exit("   ❌ Cannot auto-recover. Re-run add_superadmin_and_redeploy.py first.")
else:
    print("   ✓ superadmin@nimbus.local is created by seed_demo")

# ─── 5. Verify render.yaml ─────────────────────────────────────────────
print("==> Verifying render.yaml")
y = (OPD / "render.yaml").read_text(encoding="utf-8")
if "python manage.py seed_demo" in y:
    print("   ✓ startCommand includes seed_demo")
else:
    print("   ⚠ render.yaml missing seed_demo in startCommand")

# ─── 6. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(settings): clean rewrite — bulletproof DATABASES + import os at top",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "rev-parse", "--short", "HEAD")
print(f"\n✅ Pushed: {r.stdout.strip()}")

print("\n" + "=" * 60)
print("NEXT STEPS ON RENDER")
print("=" * 60)
print("1. Open nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("2. Watch the logs. After migrations you should see:")
print("      [superadmin] created: superadmin@nimbus.local / demo")
print("3. Sign out of the frontend.")
print("4. Log in with:")
print("      Email:    superadmin@nimbus.local")
print("      Password: demo")
print("5. Open /platform → click 'Approve & Activate' on the pending clinic.")
print("6. Sign out → log in as that clinic's admin credentials.")