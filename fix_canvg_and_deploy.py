#!/usr/bin/env python3
"""
fix_canvg_and_deploy.py
  Continues from fix_cashflow_and_add_exports.py.
  The previous script patched api/accounting_reports.py, installed
  jspdf/jspdf-autotable/xlsx, created src/utils/export.ts, and updated
  FinancialReports.tsx — but the Vite build failed because jspdf
  dynamically imports "canvg", which Rollup cannot resolve.

  This script:
    1. Installs canvg in the frontend.
    2. Re-runs the Vite build.
    3. If the build still fails, patches vite.config.* with optimizeDeps
       (include: jspdf, jspdf-autotable, canvg) + a global -> globalThis
       polyfill, then rebuilds.
    4. Commits and pushes.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"

# ── helpers ──────────────────────────────────────────────────────────
def npm_path() -> str | None:
    p = shutil.which("npm")
    if p:
        return p
    for cand in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "Documents" / "django" / "nodejs" / "npm",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if cand.exists():
            return str(cand)
    return None

def run(cmd, *, cwd=ROOT, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=cwd)

# ── 1. locate npm & install canvg ────────────────────────────────────
npm = npm_path()
if not npm:
    sys.exit("npm not found on PATH")
print(f"==> Using npm: {npm}")
print("\n==> Installing canvg (required by jspdf dynamic import)")
run([npm, "install", "canvg"], cwd=FRONTEND)

# ── 2. build (attempt #1) ────────────────────────────────────────────
def vite_build() -> bool:
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    print("\n==> Running local Vite build")
    r = subprocess.run(
        [npm, "run", "build"],
        cwd=FRONTEND, capture_output=True, text=True, env=env,
    )
    if r.returncode == 0:
        print("   ✓ Build succeeded")
        return True
    print("   ❌ Build failed:")
    for line in (r.stdout + r.stderr).splitlines()[-20:]:
        print("     " + line)
    return False

ok = vite_build()

# ── 3. if still failing, patch vite.config ──────────────────────────
if not ok:
    print("\n==> Build still failing — patching vite config with optimizeDeps")
    cfg_candidates = [
        FRONTEND / "vite.config.ts",
        FRONTEND / "vite.config.js",
        FRONTEND / "vite.config.mjs",
    ]
    cfg = next((c for c in cfg_candidates if c.exists()), None)
    if not cfg:
        sys.exit("vite.config.* not found in frontend/")

    src = cfg.read_text(encoding="utf-8")
    if "optimizeDeps" in src:
        print(f"   {cfg.name} already has optimizeDeps — leaving as-is")
    else:
        needle = "defineConfig({"
        if needle not in src:
            sys.exit(f"Cannot find '{needle}' in {cfg.name}")
        inject = (
            "defineConfig({\n"
            "  optimizeDeps: {\n"
            "    include: ['jspdf', 'jspdf-autotable', 'canvg'],\n"
            "    esbuildOptions: { define: { global: 'globalThis' } },\n"
            "  },"
        )
        src = src.replace(needle, inject, 1)
        cfg.write_text(src, encoding="utf-8")
        print(f"   patched {cfg.name}")

    if not vite_build():
        sys.exit("Build still failing after installing canvg + patching config")

# ── 4. commit & push ─────────────────────────────────────────────────
print("\n==> Staging changes")
run(["git", "add", "."])

status = subprocess.run(
    ["git", "status", "--porcelain"], cwd=ROOT,
    capture_output=True, text=True,
).stdout.strip()

if status:
    print("\n==> Committing")
    run(["git", "commit", "-m",
         "fix(frontend): install canvg for jspdf; add PDF/Excel exports to reports"])
else:
    print("   (nothing to commit)")

print("\n==> Pushing to origin/main")
run(["git", "push", "origin", "main"])

print("\n✅ Done.")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend  → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")