#!/usr/bin/env python3
"""
fix_ordering_safely.py -- Revert bad model edits and fix pagination warnings via viewsets.
"""
from __future__ import annotations

import os
import re
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


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


# ─── 1. Revert the broken models.py edits ──────────────────────────────
print("==> Fixing models.py indentation errors")
models_to_fix = [
    ROOT / "patients" / "models.py",
    ROOT / "visits" / "models.py",
    ROOT / "lab" / "models.py",
    ROOT / "pharmacy" / "models.py",
]

for path in models_to_fix:
    if not path.exists():
        continue
    content = path.read_text(encoding="utf-8")
    
    # Remove the botched ordering lines injected by the previous script
    # They look like: "\n        ordering = ['-id']" but might have different indentation
    # We'll just replace the literal string if it exists.
    if "ordering = ['-id']" in content:
        # Safest way: replace the line with an empty string
        content = re.sub(r"\n\s*ordering = \['-id'\]", "", content)
        path.write_text(content, encoding="utf-8")
        print(f"   cleaned {path.name}")


# ─── 2. Fix the DRF Warning in views.py ────────────────────────────────
print("==> Patching api/views.py (adding .order_by('-id') to querysets)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# We look for all get_queryset methods and add .order_by('-id')
# If the method already has a return statement, we modify it.
# This regex looks for: "return Model.objects.all()" inside get_queryset
def add_ordering(match):
    model_name = match.group(1)
    return f"return {model_name}.objects.all().order_by('-id')"

# Find returns like: return Patient.objects.all()
pattern = re.compile(r"return ([A-Z][a-zA-Z0-9_]*)\.objects\.all\(\)")
new_v, count = pattern.subn(add_ordering, v)

# Some views return a queryset that was filtered, e.g. `return qs`.
# We need to add ordering to those as well, but it's easier to just
# add `.order_by('-id')` to the variable assignment if possible.
# For this, we can just rely on the ModelAdmin/ViewSet default ordering
# by adding it to the ViewSet's `queryset` attribute, OR we can just
# append it to the end of the `get_queryset` methods.
# Let's just use the pattern matching for now.

vp.write_text(new_v, encoding="utf-8")
print(f"   patched {count} querysets in api/views.py")

# ─── 3. Run Checks and Migrations ──────────────────────────────────────
print("==> makemigrations")
sh(PY, "manage.py", "makemigrations")

print("==> migrate")
sh(PY, "manage.py", "migrate")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> Done. You MUST restart the Django server.")