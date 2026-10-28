#!/usr/bin/env python3
"""
fix_stray_backslash.py
  - Strips any stray leading backslash from page files
  - Verifies all App.tsx imports still resolve
  - Pushes
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

FRONTEND = OPD / "frontend"
PAGES = FRONTEND / "src" / "pages"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

# ─── 1. Scan all .tsx files for a stray leading backslash ──────────────
print("==> Scanning all page files for stray leading backslash")
fixed = []
for f in sorted(PAGES.glob("*.tsx")):
    raw = f.read_bytes()
    if raw.startswith(b"\\\r\n") or raw.startswith(b"\\\n"):
        # Strip the first backslash + newline
        if raw.startswith(b"\\\r\n"):
            raw = raw[3:]
        else:
            raw = raw[2:]
        f.write_bytes(raw)
        print(f"   FIXED: {f.name}")
        fixed.append(f.name)
    elif raw.startswith(b"\\"):
        print(f"   ⚠  {f.name} starts with backslash but no clean newline — checking manually")

if not fixed:
    print("   No stray leading backslashes found")
else:
    print(f"   Fixed {len(fixed)} file(s)")

# ─── 2. Also scan other source dirs just in case ───────────────────────
print("\n==> Scanning src/ subfolders for stray leading backslashes")
for subdir in ["components", "api", ""]:
    d = FRONTEND / "src" / subdir
    if not d.exists() or not d.is_dir():
        continue
    for f in d.glob("*.ts*"):
        raw = f.read_bytes()
        if raw.startswith(b"\\\r\n") or raw.startswith(b"\\\n"):
            if raw.startswith(b"\\\r\n"):
                raw = raw[3:]
            else:
                raw = raw[2:]
            f.write_bytes(raw)
            print(f"   FIXED: {subdir}/{f.name}")

# ─── 3. Verify every App.tsx import resolves ───────────────────────────
print("\n==> Verifying all App.tsx imports resolve to real files")
app_content = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
import_pattern = re.compile(r'import\s+\w+\s+from\s+["\'](\./[^"\']+)["\']')
imports = import_pattern.findall(app_content)

missing = []
for rel_path in imports:
    clean = rel_path.lstrip("./")
    candidates = [
        FRONTEND / "src" / f"{clean}.tsx",
        FRONTEND / "src" / f"{clean}.ts",
    ]
    if not any(c.exists() for c in candidates):
        missing.append(rel_path)

if missing:
    print("   ❌ Missing imports:")
    for m in missing:
        print(f"      {m}")
    sys.exit(1)
print(f"   ✓ All {len(imports)} imports resolve")

# ─── 4. Sanity check: verify no file starts with a bare backslash ──────
print("\n==> Final sanity check on all page files")
problems = []
for f in sorted(PAGES.glob("*.tsx")):
    first_bytes = f.read_bytes()[:20]
    if first_bytes.startswith(b"\\"):
        problems.append(f.name)
if problems:
    print("   ❌ Still have leading backslashes:")
    for p in problems:
        print(f"      {p}")
    sys.exit(1)
print("   ✓ All page files start cleanly")

# ─── 5. Verify Django still works locally (unchanged but prudent) ──────
PY = OPD / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
print("\n==> Django check (should still pass)")
r = subprocess.run([str(PY), "manage.py", "check"], cwd=OPD,
                   capture_output=True, text=True)
if r.returncode != 0:
    print("   ❌ Django check failed")
    print(r.stderr[-1000:])
    sys.exit(1)
print("   ✓ Django check OK")

# ─── 6. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(frontend): strip stray leading backslash from page files",
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
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")