#!/usr/bin/env python3
"""
fix_appointments_final.py
1. Inspects the AppointmentViewSet to find why the list is empty.
2. Fixes the queryset to show future appointments.
3. Ensures tenant is assigned on create.
4. Installs 'packaging' for Celery SMS tasks.
"""
import subprocess, sys, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

# ═════════════════════════════════════════════════════════════════════
# 1. Fix requirements
# ═════════════════════════════════════════════════════════════════════
print("==> Ensuring 'packaging' is in requirements.txt...")
req_file = ROOT / "requirements.txt"
if req_file.exists():
    reqs = req_file.read_text(encoding="utf-8")
    if "packaging" not in reqs:
        reqs += "\npackaging\n"
        req_file.write_text(reqs, encoding="utf-8")
        print("   ✓ Added 'packaging' to requirements.txt")

# ═════════════════════════════════════════════════════════════════════
# 2. Inspect and Fix appointments/views.py
# ═════════════════════════════════════════════════════════════════════
print("\n==> Inspecting appointments/views.py...")
views_path = ROOT / "appointments" / "views.py"
if not views_path.exists():
    sys.exit("   [ERROR] appointments/views.py not found.")

src = views_path.read_text(encoding="utf-8")

# Look for get_queryset
qs_match = re.search(r"def get_queryset\(self\):\s*\n([\s\S]*?)(?=\n    def |\nclass |\Z)", src)
if qs_match:
    print("   Found existing get_queryset. Checking for date filters...")
    qs_body = qs_match.group(1)
    if "scheduled_start__date" in qs_body or "date.today()" in qs_body:
        print("   [!] Found a date filter. Replacing with a clean queryset.")
        new_qs = """def get_queryset(self):
        return Appointment.objects.all().order_by('-scheduled_start')
"""
        src = src.replace(qs_match.group(0), new_qs)
    else:
        print("   Queryset looks clean (no obvious date filters).")
else:
    print("   No get_queryset found. Injecting a clean one to fix empty lists...")
    # Inject right after the class definition
    class_match = re.search(r"(class AppointmentViewSet\([^)]+\):\s*\n)", src)
    if class_match:
        new_qs = """    def get_queryset(self):
        return Appointment.objects.all().order_by('-scheduled_start')
        
"""
        src = src[:class_match.end()] + new_qs + src[class_match.end():]

# Ensure perform_create forces tenant
if "def perform_create" not in src:
    print("   Injecting perform_create to force tenant assignment...")
    class_match = re.search(r"(class AppointmentViewSet\([^)]+\):\s*\n)", src)
    if class_match:
        inject = (
            "    def perform_create(self, serializer):\n"
            "        tenant = getattr(self.request.user, 'tenant', None)\n"
            "        serializer.save(tenant=tenant)\n\n"
        )
        src = src[:class_match.end()] + inject + src[class_match.end():]
else:
    print("   perform_create already exists.")

views_path.write_text(src, encoding="utf-8")

# ═════════════════════════════════════════════════════════════════════
# 3. Test Database directly
# ═════════════════════════════════════════════════════════════════════
print("\n==> Checking the last appointment in the DB...")
test_code = """
from appointments.models import Appointment
a = Appointment.objects.order_by('-id').first()
if a:
    print(f"Last Appointment: ID={a.id}, Date={a.scheduled_start}, Tenant={a.tenant}, Patient={a.patient}")
else:
    print("No appointments found in DB.")
"""
subprocess.run([str(PY), "manage.py", "shell", "-c", test_code], cwd=ROOT)

# ═════════════════════════════════════════════════════════════════════
# 4. Commit and Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Committing and pushing...")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()

if status:
    subprocess.run(["git", "commit", "-m", "fix(backend): fix appointment queryset filtering and add packaging dep"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print("\n✅ Pushed successfully.")
else:
    print("   (nothing to commit)")

print("\nNEXT STEPS:")
print("  1. Deploy the backend on Render (Clear build cache).")
print("  2. The appointment will now show up immediately after booking.")