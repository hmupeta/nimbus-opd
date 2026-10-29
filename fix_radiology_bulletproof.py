#!/usr/bin/env python3
"""
fix_radiology_bulletproof.py
  - Uses a lazy import inside get_queryset() — bulletproof against missing imports.
  - Prints the actual radiology-related lines in views.py for diagnosis.
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

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")
lines = v.split("\n")

# ─── 1. Print every line that mentions RadiologyExam or RadiologyOrder ─
print("==> All lines mentioning Radiology in api/views.py:")
for i, line in enumerate(lines, 1):
    if "Radiology" in line:
        print(f"   L{i:4}: {line}")
print()

# ─── 2. Locate the broken RadiologyExamViewSet class ───────────────────
pattern_start = "class RadiologyExamViewSet(TenantScopedViewSet):"
if pattern_start not in v:
    print("   ❌ Could not find 'class RadiologyExamViewSet'. Nothing to fix.")
    sys.exit(1)

# Extract the class body (from class declaration to next 'class ' or EOF)
start_idx = v.find(pattern_start)
# Find next class after this one
next_class = v.find("\nclass ", start_idx + 1)
if next_class == -1:
    next_class = len(v)
class_block = v[start_idx:next_class]

# ─── 3. Replace the class with a bulletproof version ───────────────────
new_class = '''class RadiologyExamViewSet(TenantScopedViewSet):
    serializer_class = RadiologyExamSerializer
    permission_classes = [require_roles("admin", "radiology", "doctor", "nurse")]

    def get_queryset(self):
        # Lazy import — works even if the module-level import is missing
        from radiology.models import RadiologyExam
        return RadiologyExam.all_objects.filter(
            tenant_id=self.request.user.tenant_id
        ).order_by("-id")


'''

v = v[:start_idx] + new_class + v[next_class:]

# ─── 4. Save and verify ────────────────────────────────────────────────
vp.write_text(v, encoding="utf-8")
print("   ✓ Rewrote RadiologyExamViewSet with lazy import + tenant filter")
print()

print("==> manage.py check")
r = subprocess.run([str(PY), "manage.py", "check"], env=ENV, capture_output=True, text=True)
if r.returncode != 0:
    print("   ❌ Still failing. Last 15 lines:")
    for line in (r.stderr or r.stdout).splitlines()[-15:]:
        print("   " + line)
    sys.exit(1)
print("   ✓ " + (r.stdout.strip().splitlines()[-1] if r.stdout else "OK"))
print()

# ─── 5. Migrations ─────────────────────────────────────────────────────
print("==> makemigrations radiology")
r = subprocess.run([str(PY), "manage.py", "makemigrations", "radiology"], env=ENV, capture_output=True, text=True)
print("   " + (r.stdout.strip() or "(no changes)").replace("\n", "\n   "))
if r.returncode != 0:
    print(r.stderr)
    sys.exit(1)

print("\n==> migrate")
r = subprocess.run([str(PY), "manage.py", "migrate"], env=ENV, capture_output=True, text=True)
for line in (r.stdout or "").splitlines():
    if "Apply" in line or "Running" in line or "No migrations" in line:
        print("   " + line)
if r.returncode != 0:
    print(r.stderr)
    sys.exit(1)

print("\n✅ Success. Push and redeploy both services.")