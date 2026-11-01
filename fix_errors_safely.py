#!/usr/bin/env python3
"""
fix_errors_safely.py
1. Reverts the broken Staff page file.
2. Runs the missing migrations.
3. Adds a global Axios interceptor to show API errors.
"""
import os, subprocess, sys, shutil
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def sh(*cmd, cwd=ROOT, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=cwd, check=check)

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

# ═════════════════════════════════════════════════════════════════════
# 1. Revert the broken frontend file
# ═════════════════════════════════════════════════════════════════════
print("==> Reverting broken frontend file")
# Find the broken file
broken_file = None
for p in FRONTEND.glob("src/**/*.tsx"):
    if "onError: (err: any) => alert" in p.read_text(encoding="utf-8"):
        broken_file = p
        break

if broken_file:
    rel_path = broken_file.relative_to(ROOT)
    print(f"   Reverting {rel_path}")
    subprocess.run(["git", "checkout", "--", str(rel_path)], cwd=ROOT, check=True)
else:
    print("   No broken file found to revert.")

# ═════════════════════════════════════════════════════════════════════
# 2. Run Migrations (This fixes the 400 error)
# ═════════════════════════════════════════════════════════════════════
print("\n==> Applying database migrations for the new roles")
sh(str(PY), "manage.py", "makemigrations")
sh(str(PY), "manage.py", "migrate")

# ═════════════════════════════════════════════════════════════════════
# 3. Add Global Error Interceptor to API Client
# ═════════════════════════════════════════════════════════════════════
print("\n==> Adding global error alert to API client")
client_file = FRONTEND / "src" / "api" / "client.ts"
if not client_file.exists():
    client_file = FRONTEND / "src" / "api" / "client.tsx"

if client_file.exists():
    txt = client_file.read_text(encoding="utf-8")
    if "response.use" not in txt:
        # Find the end of the file or the main export to append to
        inject = """
// Global error interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data
      ? JSON.stringify(error.response.data)
      : error.message;
    // Don't alert on 401 (unauthorized) to avoid loops, handled by auth
    if (error.response?.status !== 401) {
      alert(`API Error: ${msg}`);
    }
    return Promise.reject(error);
  }
);
"""
        txt += "\n" + inject
        client_file.write_text(txt, encoding="utf-8")
        print(f"   Injected interceptor into {client_file.relative_to(FRONTEND)}")
    else:
        print("   Interceptor already exists.")
else:
    print("   [WARN] Could not find src/api/client.ts")

# ═════════════════════════════════════════════════════════════════════
# 4. Build & Push
# ═════════════════════════════════════════════════════════════════════
npm = npm_path()
if npm:
    print("\n==> Running Vite build")
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND,
                       capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ build OK")
    else:
        print("   ❌ build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print("     " + line)
        sys.exit(1)

print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "fix: revert broken UI injection and add global API error handler"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend  → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")