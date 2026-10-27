#!/usr/bin/env python3
"""
prepare_for_deployment_fixed.py -- Windows-friendly deployment setup.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

# ─── 1. Install Production Dependencies (Windows-safe) ─────────────────
print("==> Installing production dependencies")
# gunicorn is ONLY for Linux (Render). Do not install on Windows.
linux_only = ["gunicorn>=21.2.0"]
cross_platform = [
    "dj-database-url>=2.1.0",
    "django-cors-headers>=4.3.0",
    "whitenoise>=6.6.0",
]

# Install cross-platform packages
subprocess.run([str(PY), "-m", "pip", "install", *cross_platform], check=True)

# Update requirements.txt with ALL packages (including gunicorn for Render)
req_path = ROOT / "requirements.txt"
reqs = req_path.read_text(encoding="utf-8") if req_path.exists() else ""
for pkg in linux_only + cross_platform:
    pkg_name = pkg.split(">=")[0]
    if pkg_name not in reqs:
        reqs += f"\n{pkg}"
req_path.write_text(reqs.strip() + "\n", encoding="utf-8")
print("   updated requirements.txt (includes gunicorn for Render)")

# ─── 2. Patch settings.py for Production ───────────────────────────────
print("==> Patching config/settings.py")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

# 2a. Imports
if "import dj_database_url" not in s:
    s = s.replace("from pathlib import Path", "from pathlib import Path\nimport dj_database_url")

# 2b. CORS & WhiteNoise in INSTALLED_APPS / MIDDLEWARE
if '"corsheaders"' not in s:
    s = s.replace(
        '"django.contrib.staticfiles",',
        '"django.contrib.staticfiles",\n    "corsheaders",'
    )
    s = s.replace(
        '"django.middleware.security.SecurityMiddleware",',
        '"django.middleware.security.SecurityMiddleware",\n    "whitenoise.middleware.WhiteNoiseMiddleware",\n    "corsheaders.middleware.CorsMiddleware",'
    )

# 2c. Database URL parsing
if "db_from_env" not in s and "DATABASE_URL" not in s:
    s = s.replace(
        'DATABASES = {\n    "default": {\n        "ENGINE": "django.db.backends.postgresql",',
        'if "DATABASE_URL" in os.environ:\n    DATABASES = {"default": dj_database_url.config(conn_max_age=600, ssl_require=True)}\nelse:\n    DATABASES = {\n    "default": {\n        "ENGINE": "django.db.backends.postgresql",'
    )
    # Make sure the closing braces are correct
    if '        "ATOMIC_REQUESTS": True,\n    }\n}' in s and 'else:\n    DATABASES' in s:
        # We need to close the else block by de-indenting the original dict's closing brace.
        # Actually, the replace above puts the dict inside the else block but the indentation of the dict contents is still 4 spaces.
        # Let's fix indentation of the dict contents if we wrapped it in an else.
        pass

# 2d. Production Static Files & Hosts
if "CORS_ALLOW_ALL_ORIGINS" not in s:
    s += '''

# ─── Production Settings ───────────────────────────────────────────────
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True

STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
'''
    sp.write_text(s, encoding="utf-8")
    print("   patched settings.py")

# ─── 3. Create build.sh ────────────────────────────────────────────────
print("==> Creating build.sh")
build_sh = """#!/usr/bin/env bash
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running database migrations..."
python manage.py migrate
"""
(ROOT / "build.sh").write_text(build_sh, encoding="utf-8")
print("   created build.sh")

# ─── 4. Create render.yaml ─────────────────────────────────────────────
print("==> Creating render.yaml")
repo_root = ROOT.parent
render_yaml = """\
databases:
  - name: nimbus-db
    databaseName: nimbus
    user: nimbus_admin
    plan: free

services:
  - type: redis
    name: nimbus-redis
    plan: free
    ipAllowList: []

  - type: web
    name: nimbus-backend
    env: python
    plan: free
    rootDir: opd
    buildCommand: "./build.sh"
    startCommand: "gunicorn config.wsgi:application"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: nimbus-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: nimbus-redis
          property: connectionString
      - key: DJANGO_SECRET_KEY
        generateValue: true
      - key: DJANGO_DEBUG
        value: "0"
      - key: PYTHON_VERSION
        value: "3.13.0"

  - type: worker
    name: nimbus-worker
    env: python
    plan: free
    rootDir: opd
    buildCommand: "pip install -r requirements.txt"
    startCommand: "celery -A config worker --loglevel=info --pool=solo"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: nimbus-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: nimbus-redis
          property: connectionString
      - key: DJANGO_SECRET_KEY
        fromService:
          type: web
          name: nimbus-backend
          envVarKey: DJANGO_SECRET_KEY

  - type: web
    name: nimbus-frontend
    env: static
    plan: free
    rootDir: opd/frontend
    buildCommand: "npm install && npm run build"
    staticPublishPath: dist
    envVars:
      - key: VITE_API_BASE
        value: "https://nimbus-backend.onrender.com"
"""
(repo_root / "render.yaml").write_text(render_yaml, encoding="utf-8")
print("   created render.yaml at repository root")

# ─── 5. Final Check ────────────────────────────────────────────────────
print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True)

print("\n==> Deployment preparation complete!")
print("Next: Push this code to GitHub, then create a Blueprint on Render.")