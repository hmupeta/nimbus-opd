#!/usr/bin/env python3
"""
add_debug_exception_handler.py
  - Adds a custom DRF exception handler that returns the full Python traceback on 500 errors.
  - Updates settings.py to use this handler.
  - Pushes to GitHub.
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

# ─── 1. Create the custom exception handler ────────────────────────────
print("==> Creating api/exceptions.py")
exc_path = OPD / "api" / "exceptions.py"
exc_path.write_text('''\
from rest_framework.views import exception_handler
from rest_framework.response import Response
import traceback

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    # If response is None, it means Django raised an unhandled 500 error.
    # We catch it, print it to the Render logs, and return it as JSON.
    if response is None:
        print("\\n--- UNHANDLED EXCEPTION ---")
        print(traceback.format_exc())
        print("---------------------------\\n")
        
        return Response({
            "detail": str(exc),
            "traceback": traceback.format_exc()
        }, status=500)
        
    return response
''', encoding="utf-8")
print("   wrote api/exceptions.py")

# ─── 2. Update settings.py to use the handler ──────────────────────────
print("==> Updating config/settings.py")
sp = OPD / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

if '"EXCEPTION_HANDLER"' not in s:
    s = s.replace(
        '"DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",',
        '"DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",\n    "EXCEPTION_HANDLER": "api.exceptions.custom_exception_handler",'
    )
    sp.write_text(s, encoding="utf-8")
    print("   added custom exception handler to REST_FRAMEWORK")

# ─── 3. Fix the ordering warnings in UserViewSet and PatientViewSet ────
print("==> Fixing pagination warnings in api/views.py")
vp = OPD / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Fix UserViewSet ordering
if "qs = User.objects.filter(tenant=t).order_by" not in v:
    v = v.replace(
        "qs = User.objects.filter(tenant=t)",
        "qs = User.objects.filter(tenant=t).order_by('-id')"
    )

# Fix PatientViewSet ordering
if "qs = Patient.objects.all().order_by" not in v:
    v = v.replace(
        "qs = Patient.objects.all()",
        "qs = Patient.objects.all().order_by('-id')"
    )

vp.write_text(v, encoding="utf-8")
print("   added .order_by('-id') to views")

# ─── 4. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "feat(api): return full traceback on 500 errors for debugging",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. Wait for the backend to go Live.")
print("  3. Go to the frontend and try to create a patient again.")
print("  4. If it fails, open Chrome DevTools (F12) → Network tab → click the red 'patients' request → look at the 'Response' tab.")
print("     It will now show the exact Python traceback causing the crash.")