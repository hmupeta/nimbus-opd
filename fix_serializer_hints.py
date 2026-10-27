#!/usr/bin/env python3
"""
fix_serializer_hints.py -- add `-> bool` return type hints to the
    SerializerMethodField getters in momo_serializers and gateway_serializers.
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


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


def patch_file(path: Path, replacements: list[tuple[str, str]]) -> int:
    """Apply literal replacements; return number actually applied."""
    if not path.exists():
        print(f"   [skip] {path.name} not found")
        return 0
    src = path.read_text(encoding="utf-8")
    applied = 0
    for old, new in replacements:
        if old in src:
            src = src.replace(old, new)
            applied += 1
    if applied:
        path.write_text(src, encoding="utf-8")
    print(f"   {path.name}: {applied}/{len(replacements)} patch(es) applied")
    return applied


# ─── 1. momo_serializers.py ────────────────────────────────────────────
patch_file(ROOT / "api" / "momo_serializers.py", [
    (
        "    def get_api_key_set(self, obj):          return bool(obj.api_key)",
        "    def get_api_key_set(self, obj) -> bool:          return bool(obj.api_key)",
    ),
    (
        "    def get_api_secret_set(self, obj):       return bool(obj.api_secret)",
        "    def get_api_secret_set(self, obj) -> bool:       return bool(obj.api_secret)",
    ),
    (
        "    def get_api_password_set(self, obj):     return bool(obj.api_password)",
        "    def get_api_password_set(self, obj) -> bool:     return bool(obj.api_password)",
    ),
    (
        "    def get_subscription_key_set(self, obj): return bool(obj.subscription_key)",
        "    def get_subscription_key_set(self, obj) -> bool: return bool(obj.subscription_key)",
    ),
])

# ─── 2. gateway_serializers.py ─────────────────────────────────────────
patch_file(ROOT / "api" / "gateway_serializers.py", [
    (
        "    def get_secret_key_set(self, obj): return bool(obj.secret_key)",
        "    def get_secret_key_set(self, obj) -> bool: return bool(obj.secret_key)",
    ),
    (
        "    def get_webhook_secret_set(self, obj): return bool(obj.webhook_secret)",
        "    def get_webhook_secret_set(self, obj) -> bool: return bool(obj.webhook_secret)",
    ),
])

# ─── 3. Verify ─────────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> Verifying schema (Warnings should be 0)")
sh(PY, "manage.py", "spectacular", "--file", "-")

print()
print("==> Done.")