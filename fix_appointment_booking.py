#!/usr/bin/env python3
"""
fix_appointment_booking.py
1. Adds missing 'packaging' module to requirements.txt.
2. Patches AppointmentViewSet to force tenant assignment.
3. Builds and pushes.
"""
import subprocess, sys, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

# ═════════════════════════════════════════════════════════════════════
# 1. Fix Requirements
# ═════════════════════════════════════════════════════════════════════
print("==> Checking requirements.txt...")
req_file = ROOT / "requirements.txt"
if req_file.exists():
    reqs = req_file.read_text(encoding="utf-8")
    if "packaging" not in reqs:
        reqs += "\npackaging\n"
        req_file.write_text(reqs, encoding="utf-8")
        print("   ✓ Added 'packaging' to requirements.txt")
    else:
        print("   'packaging' already in requirements.txt")

# ═════════════════════════════════════════════════════════════════════
# 2. Patch AppointmentViewSet
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching appointments/views.py...")
views_path = ROOT / "appointments" / "views.py"
if views_path.exists():
    src = views_path.read_text(encoding="utf-8")
    if "class AppointmentViewSet" in src:
        if "def perform_create" not in src:
            match = re.search(r"(class AppointmentViewSet\([^)]+\):\s*\n)", src)
            if match:
                inject = (
                    "    def perform_create(self, serializer):\n"
                    "        tenant = getattr(self.request.user, 'tenant', None)\n"
                    "        serializer.save(tenant=tenant)\n\n"
                )
                src = src[:match.end()] + inject + src[match.end():]
                views_path.write_text(src, encoding="utf-8")
                print("   ✓ Injected perform_create to force tenant assignment.")
        else:
            print("   perform_create already exists.")
    else:
        print("   [WARN] Could not find AppointmentViewSet.")
else:
    print("   [WARN] appointments/views.py not found.")

# ═════════════════════════════════════════════════════════════════════
# 3. Commit and Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Committing and pushing...")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()

if status:
    subprocess.run(["git", "commit", "-m", "fix(backend): add missing packaging dep and fix appointment tenant creation"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print("\n✅ Pushed successfully.")
else:
    print("   (nothing to commit)")

print("\nNEXT STEPS:")
print("  1. Deploy the backend on Render (Clear build cache).")
print("  2. The appointment creation will now save the clinic automatically.")
print("  3. The 'packaging' error in the logs will be gone.")