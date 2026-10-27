#!/usr/bin/env python3
"""
finish_superadmin_push.py -- Fix local settings.DATABASES, verify the patch,
                             and push WITHOUT running seed locally.
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

# ─── 1. Fix DATABASES block in settings.py (local dev + Render) ────────
print("==> Fixing DATABASES block in config/settings.py")
sp = OPD / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

# Replace whatever DATABASES block exists with a bulletproof one
pattern = re.compile(r"DATABASES\s*=\s*\{.*?\n\}\n(?:.*?\n)*?(?=\n[A-Z_]+\s*=|\Z)", re.DOTALL)
# safer: match just up to the closing brace of the dict
pattern = re.compile(r"DATABASES\s*=\s*\{[^}]*\}\n", re.DOTALL)

new_block = '''DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     os.environ.get("DB_NAME", "opd"),
        "USER":     os.environ.get("DB_USER", "opd_owner"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "opd_owner"),
        "HOST":     os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT":     os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "ATOMIC_REQUESTS": True,
    }
}

# On Render, DATABASE_URL is provided automatically. It overrides the local config above.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    DATABASES["default"] = dj_database_url.parse(
        _database_url,
        conn_max_age=600,
        ssl_require=True,
    )
'''

# Ensure dj_database_url import
if "import dj_database_url" not in s:
    s = s.replace("from pathlib import Path",
                  "from pathlib import Path\nimport os\nimport dj_database_url")

s = pattern.sub(new_block, s, count=1)
sp.write_text(s, encoding="utf-8")
print("   DATABASES block replaced with bulletproof config")

# ─── 2. Verify Django loads locally ────────────────────────────────────
print("==> Verifying local Django config")
PY = OPD / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
r = subprocess.run([str(PY), "manage.py", "check"],
                   cwd=OPD, capture_output=True, text=True)
if r.returncode != 0:
    print("   ✗ Local Django check failed:")
    print(r.stderr[-2000:])
    sys.exit(1)
print("   ✓ Local Django config loads cleanly")

# ─── 3. Verify the seed_demo patch is on disk ──────────────────────────
print("==> Verifying seed_demo patch")
seed = OPD / "tenants" / "management" / "commands" / "seed_demo.py"
seed_content = seed.read_text(encoding="utf-8")
checks = {
    "_ensure_superadmin method": "_ensure_superadmin" in seed_content,
    "superadmin created": "superadmin@nimbus.local" in seed_content,
    "handle() calls it": "self._ensure_superadmin()" in seed_content,
}
for label, ok in checks.items():
    print(f"   [{'✓' if ok else '✗'}] {label}")
    if not ok:
        sys.exit(f"seed_demo.py is missing: {label}")

# ─── 4. Verify render.yaml has the seed-on-boot command ────────────────
print("==> Verifying render.yaml")
ry = OPD / "render.yaml"
y = ry.read_text(encoding="utf-8")
if "python manage.py seed_demo" in y:
    print("   ✓ startCommand includes 'seed_demo'")
else:
    print("   ✗ render.yaml startCommand missing 'seed_demo'")
    sys.exit(1)

# ─── 5. Commit and push ────────────────────────────────────────────────
print("\n==> Staging")
sh("git", "add", ".")

print("==> Committing")
r = sh("git", "commit", "-m",
       "feat(seed): auto-create superadmin@nimbus.local + bulletproof DATABASES config",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

print("==> Pushing to origin/main")
r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "rev-parse", "--short", "HEAD")
print(f"\n==> New commit pushed: {r.stdout.strip()}")

print("\n" + "=" * 60)
print("NEXT STEPS ON RENDER:")
print("=" * 60)
print("1. Open nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("2. Watch the logs. You should see:")
print("      [superadmin] created: superadmin@nimbus.local / demo")
print("3. Sign out of the frontend.")
print("4. Log in with:")
print("      Email:    superadmin@nimbus.local")
print("      Password: demo")
print("5. Open /platform → approve the pending clinic.")
print("6. Sign out, log in with THAT clinic's admin credentials.")