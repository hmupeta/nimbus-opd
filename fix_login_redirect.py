#!/usr/bin/env python3
"""
fix_login_redirect.py -- Update Login.tsx to redirect to /dashboard instead of /.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
FRONTEND = ROOT / "frontend"
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

lp = FRONTEND / "src" / "pages" / "Login.tsx"
l = lp.read_text(encoding="utf-8")

# The old code navigates to "/"
old_code = 'nav("/", { replace: true });'
new_code = 'nav("/dashboard", { replace: true });'

if old_code in l:
    l = l.replace(old_code, new_code)
    lp.write_text(l, encoding="utf-8")
    print("   patched Login.tsx to redirect to /dashboard")
else:
    print("   [INFO] Login.tsx already redirects to /dashboard, or the string wasn't found.")

print("==> Done. Vite will auto-reload.")