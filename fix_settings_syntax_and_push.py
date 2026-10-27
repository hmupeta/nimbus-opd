#!/usr/bin/env python3
"""
fix_settings_syntax_and_push.py
  - Use a balanced-brace parser to replace the DATABASES block safely
  - Verify Django loads locally
  - Push to GitHub
"""
from __future__ import annotations
import re
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

sp = OPD / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

# ─── 1. Find the DATABASES = { ... } block via balanced-brace parsing ──
print("==> Finding DATABASES block via balanced-brace parsing")
start_match = re.search(r"^DATABASES\s*=\s*\{", s, re.MULTILINE)
if not start_match:
    sys.exit("❌ Could not find 'DATABASES = {' in settings.py")

start_idx = start_match.start()
brace_open_idx = s.index("{", start_match.start())

# Walk forward counting braces
depth = 0
i = brace_open_idx
while i < len(s):
    if s[i] == "{":
        depth += 1
    elif s[i] == "}":
        depth -= 1
        if depth == 0:
            break
    i += 1

if depth != 0:
    sys.exit("❌ Unbalanced braces — could not find end of DATABASES block")

end_idx = i + 1  # include the closing }
# consume trailing newline
while end_idx < len(s) and s[end_idx] == "\n":
    end_idx += 1

old_block = s[start_idx:end_idx]
print(f"   found block of {end_idx - start_idx} chars")

# ─── 2. Replace with clean, correct block ──────────────────────────────
new_block = '''DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     os.environ.get("DB_NAME", "opd"),
        "USER":     os.environ.get("DB_USER", "opd_owner"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "opd_owner"),
        "HOST":     os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT":     os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "ATOMIC_REQUESTS": True,
    }
}

# Render provides DATABASE_URL automatically. It overrides the local config above.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    DATABASES["default"] = dj_database_url.parse(
        _database_url,
        conn_max_age=600,
        ssl_require=True,
    )
'''

s_new = s[:start_idx] + new_block + s[end_idx:]

# ─── 3. Ensure imports are present ─────────────────────────────────────
if "import dj_database_url" not in s_new:
    s_new = s_new.replace(
        "from pathlib import Path",
        "from pathlib import Path\nimport os\nimport dj_database_url",
    )
elif "import os" not in s_new.split("import dj_database_url")[0]:
    # os missing — add it
    s_new = s_new.replace(
        "import dj_database_url",
        "import os\nimport dj_database_url",
        1,
    )

sp.write_text(s_new, encoding="utf-8")
print("   wrote clean DATABASES block")

# ─── 4. Verify syntax with Python parser ───────────────────────────────
print("==> Verifying Python syntax")
PY = OPD / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
r = subprocess.run([str(PY), "-c",
                    "import ast, pathlib; ast.parse(pathlib.Path('config/settings.py').read_text())"],
                   cwd=OPD, capture_output=True, text=True)
if r.returncode != 0:
    print("   ❌ Syntax still broken:")
    print(r.stderr[-1500:])
    sys.exit(1)
print("   ✓ settings.py parses as valid Python")

# ─── 5. Verify Django can actually load it ─────────────────────────────
print("==> Running manage.py check")
r = subprocess.run([str(PY), "manage.py", "check"],
                   cwd=OPD, capture_output=True, text=True)
if r.returncode != 0:
    print("   ❌ Django check failed:")
    print(r.stderr[-2000:])
    sys.exit(1)
print("   ✓ Django loads successfully")

# ─── 6. Verify seed_demo patch is intact ───────────────────────────────
print("==> Verifying seed_demo patch")
seed = OPD / "tenants" / "management" / "commands" / "seed_demo.py"
seed_content = seed.read_text(encoding="utf-8")
if "superadmin@nimbus.local" not in seed_content:
    print("   ⚠ seed_demo.py doesn't create superadmin — re-patching")
    sys.exit("Run add_superadmin_and_redeploy.py first")
print("   ✓ seed_demo creates superadmin@nimbus.local")

# ─── 7. Verify render.yaml ─────────────────────────────────────────────
print("==> Verifying render.yaml")
ry = OPD / "render.yaml"
y = ry.read_text(encoding="utf-8")
if "python manage.py seed_demo" not in y:
    sys.exit("   ❌ render.yaml startCommand missing seed_demo")
print("   ✓ render.yaml startCommand includes seed_demo")

# ─── 8. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m",
       "fix(settings): restore valid DATABASES block (balanced-brace safe)",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "rev-parse", "--short", "HEAD")
print(f"\n✅ Pushed: {r.stdout.strip()}")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. Watch for: [superadmin] created: superadmin@nimbus.local / demo")
print("  3. Sign out of frontend, log in with superadmin@nimbus.local / demo")
print("  4. Open /platform → approve pending clinic")