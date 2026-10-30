#!/usr/bin/env python3
"""
fix_accounting_serializer_import.py
  - Moves the accounting model imports to the top of api/serializers.py.
"""
from __future__ import annotations
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

ENV = __import__("os").environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

SP = ROOT / "api" / "serializers.py"
s = SP.read_text(encoding="utf-8")

# 1. Remove the bottom import if it exists
s = s.replace("from accounting.models import JournalEntry, JournalEntryLine\n", "")

# 2. Add it near the top (after the other model imports)
if "from accounting.models import" not in s.split("class ")[0]:
    # Find a safe place to inject it (after billing or tenants imports)
    if "from billing.models import" in s:
        s = s.replace(
            "from billing.models import",
            "from accounting.models import JournalEntry, JournalEntryLine\nfrom billing.models import",
            1
        )
    else:
        # Fallback: after the first non-built-in import
        s = re.sub(
            r"(from \w+\.models import [^\n]+\n)",
            r"\1from accounting.models import JournalEntry, JournalEntryLine\n",
            s, count=1
        )

SP.write_text(s, encoding="utf-8")
print("   moved accounting imports to the top of serializers.py")

# 3. Verify Django loads
print("\n==> manage.py check")
r = subprocess.run([str(PY), "manage.py", "check"], env=ENV, capture_output=True, text=True)
if r.returncode != 0:
    print("   ❌ check failed:")
    for line in (r.stderr or r.stdout).splitlines()[-15:]:
        print("   " + line)
    sys.exit(1)
print("   ✓ " + (r.stdout.strip().splitlines()[-1] if r.stdout else "OK"))

# 4. Commit and push
print("\n==> Committing and pushing")
def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT, env=ENV)

sh("git", "add", ".")
sh("git", "commit", "-m", "fix(api): move accounting model imports to top of serializers.py")
sh("git", "push", "origin", "main")

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")