#!/usr/bin/env python3
"""
fix_platform_claim.py -- Add is_platform_admin to the correct token serializer.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

tp = ROOT / "api" / "tokens.py"
t = tp.read_text(encoding="utf-8")

if 'token["is_platform_admin"]' not in t:
    t = t.replace(
        'token["full_name"] = user.get_full_name() or user.email',
        'token["full_name"] = user.get_full_name() or user.email\n        token["is_platform_admin"] = user.is_platform_admin'
    )
    tp.write_text(t, encoding="utf-8")
    print("   patched api/tokens.py (added is_platform_admin claim)")
else:
    print("   [INFO] tokens.py already contains the claim.")

print("==> Done. Restart your Django server, clear site data, and log back in.")