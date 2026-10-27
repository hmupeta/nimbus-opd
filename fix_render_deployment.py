#!/usr/bin/env python3
"""
fix_render_deployment.py -- Remove Docker, rewrite DB config, redeploy clean.
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
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD)

# ─── 1. Delete Docker files that cause Render to ignore render.yaml ────
print("==> Removing Dockerfile and docker-compose.yml")
for f in ["Dockerfile", "docker-compose.yml", "init.sql"]:
    p = OPD / f
    if p.exists():
        sh("git", "rm", "-f", f, check=False)
        p.unlink(missing_ok=True)
        print(f"   deleted {f}")

# ─── 2. Rewrite settings.py DATABASES section cleanly ──────────────────
print("==> Rewriting DATABASES config in config/settings.py")
sp = OPD / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

# Ensure dj_database_url import
if "import dj_database_url" not in s:
    s = s.replace("from pathlib import Path", "from pathlib import Path\nimport os\nimport dj_database_url")

# Find the entire DATABASES block and replace with a clean, robust version
pattern = re.compile(r"DATABASES\s*=\s*\{.*?\n\}", re.DOTALL)
new_db = '''DATABASES = {
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

# On Render, DATABASE_URL is the only DB config we need.
# This OVERRIDES the fallback above when the env var is present.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    DATABASES["default"] = dj_database_url.parse(
        _database_url,
        conn_max_age=600,
        ssl_require=True,
    )'''

s = pattern.sub(new_db, s, count=1)

# Ensure production extras at the end
if "CORS_ALLOW_ALL_ORIGINS" not in s:
    s += '''

# ─── Production overrides ─────────────────────────────────────────────
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
'''
sp.write_text(s, encoding="utf-8")
print("   rewrote DATABASES config")

# ─── 3. Verify render.yaml is correct ──────────────────────────────────
print("==> Verifying render.yaml")
ry = OPD / "render.yaml"
if not ry.exists():
    sys.exit("render.yaml missing! Cannot proceed.")

y = ry.read_text(encoding="utf-8")
checks = {
    "env: python": "env: python" in y,
    "gunicorn startCommand": "gunicorn config.wsgi:application" in y,
    "DATABASE_URL envVar": "DATABASE_URL" in y,
}
for label, ok in checks.items():
    print(f"   [{'OK' if ok else 'MISSING'}] {label}")
    if not ok:
        sys.exit(f"render.yaml is missing: {label}")

# ─── 4. Update build.sh to be more robust ──────────────────────────────
print("==> Updating build.sh")
build_sh = """#!/usr/bin/env bash
set -o errexit

echo "→ Installing dependencies..."
pip install -r requirements.txt

echo "→ Collecting static files..."
python manage.py collectstatic --no-input --clear

echo "→ Running migrations..."
python manage.py migrate --noinput

echo "→ Build complete."
"""
(OPD / "build.sh").write_text(build_sh, encoding="utf-8")
sh("git", "update-index", "--add", "--chmod=+x", "build.sh", check=False)

# ─── 5. Verify Django boots locally (sanity check) ─────────────────────
print("==> Local sanity check")
PY = OPD / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
subprocess.run([str(PY), "manage.py", "check"], check=True, cwd=OPD)

# ─── 6. Commit and push ────────────────────────────────────────────────
print("==> Committing and pushing")
sh("git", "add", ".")
sh("git", "commit", "-m",
   "fix(render): remove Docker, use Python buildpack, robust DATABASE_URL parsing",
   check=False)
sh("git", "push", "origin", "main")

print()
print("==> Done. Now on Render:")
print("   1. Go to your nimbus-backend service")
print("   2. Click 'Manual Deploy' → 'Clear build cache & deploy'")
print("   3. Watch the logs — you should now see gunicorn booting")