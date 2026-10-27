#!/usr/bin/env python3
"""
add_superadmin_and_redeploy.py
  - Patch seed_demo.py to also create superadmin@nimbus.local
  - Update render.yaml startCommand to auto-run seed on boot
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

# ─── 1. Patch seed_demo.py to create superadmin ────────────────────────
print("==> Patching seed_demo.py to create superadmin@nimbus.local")
seed = OPD / "tenants" / "management" / "commands" / "seed_demo.py"
s = seed.read_text(encoding="utf-8")

# Already added? Skip.
if "superadmin@nimbus.local" not in s:
    # Inject a superadmin creation step right before the [demo] line
    # of the handle() method, so it always runs, regardless of reset.
    marker = "    def handle(self, *args, **opts):"
    if marker not in s:
        sys.exit("Could not find handle() in seed_demo.py")

    # Find the body of handle() — we'll add our logic inside it after
    # the reset block but before _seed_demo().
    injection = '''        self._ensure_superadmin()
'''
    s = s.replace(
        "        self._seed_demo()\n",
        injection + "        self._seed_demo()\n",
        1,
    )

    # Add the helper method before `# ── tenant A ─`
    helper = '''    def _ensure_superadmin(self):
        """Ensure a Platform Admin exists with NO tenant (cannot see clinical data)."""
        from django.contrib.auth.hashers import make_password
        if User.objects.filter(email="superadmin@nimbus.local").exists():
            self.stdout.write("   [superadmin] already exists, skipping")
            return
        User.objects.create(
            email="superadmin@nimbus.local",
            password=make_password("demo"),
            first_name="Super",
            last_name="Admin",
            role="admin",
            is_staff=True,
            is_superuser=True,
            is_platform_admin=True,
            tenant=None,  # Critical: no tenant → RLS blocks all clinical data
        )
        self.stdout.write(self.style.SUCCESS(
            "   [superadmin] created: superadmin@nimbus.local / demo"))

'''
    # Anchor to the first tenant method so it's placed sensibly
    anchor = "    # ── tenant A ───────────────────────────────────────────────────────"
    if anchor in s:
        s = s.replace(anchor, helper + anchor, 1)
    else:
        # Fallback: append before class ends
        s = s.replace(
            "        self.stdout.write(self.style.SUCCESS(\"   [clinic-b] seeded\"))",
            "        self.stdout.write(self.style.SUCCESS(\"   [clinic-b] seeded\"))\n\n" + helper,
            1,
        )

    seed.write_text(s, encoding="utf-8")
    print("   patched seed_demo.py (adds _ensure_superadmin)")
else:
    print("   seed_demo.py already creates superadmin")

# ─── 2. Update render.yaml to auto-seed on startup ─────────────────────
print("==> Updating render.yaml startCommand to auto-seed")
ry = OPD / "render.yaml"
ry_content = ry.read_text(encoding="utf-8")

old_start = 'python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT'
new_start = 'python manage.py migrate --noinput && python manage.py seed_demo && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT'

if old_start in ry_content and new_start not in ry_content:
    ry_content = ry_content.replace(old_start, new_start)
    ry.write_text(ry_content, encoding="utf-8")
    print("   render.yaml: added seed_demo to startCommand")
elif new_start in ry_content:
    print("   render.yaml: already includes seed_demo")
else:
    sys.exit("Could not find startCommand line in render.yaml")

# ─── 3. Verify local seed works ────────────────────────────────────────
print("\n==> Running local seed_demo to verify (no --reset, safe)")
PY = OPD / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
r = subprocess.run([str(PY), "manage.py", "seed_demo"],
                   cwd=OPD, capture_output=True, text=True,
                   env={**__import__("os").environ, "NO_REDIS": "1"})
print("   " + (r.stdout.strip().splitlines()[-5:] if r.stdout else "no output"))
for line in (r.stdout or "").splitlines()[-5:]:
    print("   " + line)
if r.returncode != 0:
    print("   [ERR] local seed failed:")
    print(r.stderr[-1500:])
    sys.exit(1)

# ─── 4. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m",
       "feat(seed): auto-create superadmin + run seed_demo on backend startup",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "rev-parse", "--short", "HEAD")
print(f"\n==> Pushed commit: {r.stdout.strip()}")
print("\n==> Next steps on Render:")
print("   1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("   2. Watch the logs; you should see:")
print("      [superadmin] created: superadmin@nimbus.local / demo")
print("   3. Then log in at /login as superadmin@nimbus.local / demo")
print("   4. Go to /platform → Approve the pending clinic")
print("   5. That clinic's admin can now log in with THEIR credentials")