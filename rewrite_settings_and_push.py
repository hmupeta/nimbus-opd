#!/usr/bin/env python3
"""
rewrite_settings_and_push.py -- Completely rewrite config/settings.py cleanly,
                                 verify, and push.
"""
from __future__ import annotations
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

# ─── 1. Overwrite settings.py with a clean version ─────────────────────
print("==> Writing clean config/settings.py")

SETTINGS = r'''"""
Django settings for the Nimbus OPD Cloud multi-tenant project.
This file is safe for both local development and Render production.
"""
import os
from pathlib import Path

import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent


# ─── Core ──────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-insecure-CJA35NjXmo263HQv4Zu-wLBj49f3s7Kns0pEkjUPZADRreoYdbRoIAzX0ly-CR2P6dY",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]


# ─── Applications ──────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",

    # Local apps
    "api.apps.ApiConfig",
    "common",
    "tenants",
    "patients",
    "visits",
    "appointments",
    "vitals",
    "clinical",
    "lab",
    "radiology",
    "pharmacy",
    "audit.apps.AuditConfig",
    "billing",
    "notifications.apps.NotificationsConfig",
]

AUTH_USER_MODEL = "tenants.User"


# ─── Middleware ────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ─── Databases ─────────────────────────────────────────────────────────
# Local defaults (safe if you are on Windows/Postgres locally).
# On Render, DATABASE_URL overrides the entire block below.
DATABASES = {
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

# Render auto-provides DATABASE_URL. It overrides the local block above.
if os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.parse(
        os.environ["DATABASE_URL"],
        conn_max_age=600,
        ssl_require=True,
    )


# ─── Auth ──────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]


# ─── I18N / Static ─────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ─── CORS (React frontend runs on a different origin) ──────────────────
CORS_ALLOW_ALL_ORIGINS = True


# ─── DRF ───────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.auth.TenantJWTAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "api.permissions.TenantHeaderMatch",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  __import__("datetime").timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": __import__("datetime").timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":  True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES":      ("Bearer",),
}


# ─── OpenAPI / Swagger ─────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "OPD Multi-Tenant API",
    "DESCRIPTION": "Outpatient Department multi-tenant backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"jwtAuth": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "jwtAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}


# ─── Celery ────────────────────────────────────────────────────────────
# Set NO_REDIS=1 locally to run tasks synchronously (no Redis required).
CELERY_TASK_ALWAYS_EAGER = os.environ.get("NO_REDIS", "0") == "1"
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE


# ─── Email (Console backend for development) ───────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@opd-system.local"
'''

(OPD / "config" / "settings.py").write_text(SETTINGS, encoding="utf-8")
print("   wrote clean settings.py")

# ─── 2. Verify it parses ───────────────────────────────────────────────
PY = OPD / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)

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
    print(r.stderr[-2500:])
    sys.exit(1)
print("   ✓ Django loads successfully")

# ─── 4. Verify superadmin patch is still present ───────────────────────
print("==> Verifying seed_demo superadmin patch")
seed = OPD / "tenants" / "management" / "commands" / "seed_demo.py"
if "superadmin@nimbus.local" not in seed.read_text(encoding="utf-8"):
    print("   ⚠ superadmin patch missing — re-run add_superadmin_and_redeploy.py")
else:
    print("   ✓ superadmin@nimbus.local is created by seed_demo")

# ─── 5. Verify render.yaml ─────────────────────────────────────────────
print("==> Verifying render.yaml")
y = (OPD / "render.yaml").read_text(encoding="utf-8")
if "python manage.py seed_demo" not in y:
    print("   ⚠ render.yaml missing seed_demo — re-run add_superadmin_and_redeploy.py")
else:
    print("   ✓ render.yaml startCommand includes seed_demo")

# ─── 6. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m",
       "fix(settings): complete clean rewrite — valid DATABASES, no duplicate blocks",
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
print("\nNEXT ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. Watch for: [superadmin] created: superadmin@nimbus.local / demo")
print("  3. Sign out of frontend → log in as superadmin@nimbus.local / demo")
print("  4. Open /platform → approve pending clinic")