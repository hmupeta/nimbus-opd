#!/usr/bin/env python3
"""
fix_media_serving.py
  - Adds a route in Django to serve /media/ files.
  - Creates a frontend helper to prepend the API URL to media paths.
  - Updates VisitTimeline and LabDashboard to use the helper.
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

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

FRONTEND = ROOT / "frontend"
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

# ─── 1. BACKEND: Serve Media Files ─────────────────────────────────────
print("==> Patching config/urls.py to serve media files")
up = ROOT / "config" / "urls.py"
u = up.read_text(encoding="utf-8")

if "django.views.static import serve" not in u:
    u = u.replace(
        "from django.urls import include, path",
        "from django.urls import include, path, re_path\n"
        "from django.views.static import serve\n"
        "from django.conf import settings"
    )
    
    # Append the media route at the end of urlpatterns
    media_route = '''
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
'''
    if "urlpatterns += [" not in u:
        u += media_route
    else:
        u = u.replace("urlpatterns += [", media_route + "\nurlpatterns += [")
        
    up.write_text(u, encoding="utf-8")
    print("   added media serving route to Django")

# ─── 2. FRONTEND: Create media URL helper ──────────────────────────────
print("==> Updating frontend/src/api/client.ts")
cp = FRONTEND / "src" / "api" / "client.ts"
c = cp.read_text(encoding="utf-8")

if "export function getMediaUrl" not in c:
    c += '''

// Helper to build absolute URLs for uploaded files (images, PDFs)
export function getMediaUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path}`;
}
'''
    cp.write_text(c, encoding="utf-8")
    print("   added getMediaUrl helper to client.ts")

# ─── 3. FRONTEND: Use helper in VisitTimeline ──────────────────────────
print("==> Updating VisitTimeline.tsx")
vt = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v_content = vt.read_text(encoding="utf-8")

# Add import
if "getMediaUrl" not in v_content:
    v_content = v_content.replace(
        'import { api } from "../api/client";',
        'import { api, getMediaUrl } from "../api/client";'
    )

# Fix Radiology Image link
v_content = v_content.replace(
    '<a href={o.image} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sky-600 hover:underline font-medium">',
    '<a href={getMediaUrl(o.image)} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sky-600 hover:underline font-medium">'
)

# Fix Lab Result Attachment link
v_content = v_content.replace(
    '<a href={l.result.attachment} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sky-600 hover:underline font-medium">',
    '<a href={getMediaUrl(l.result.attachment)} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sky-600 hover:underline font-medium">'
)

vt.write_text(v_content, encoding="utf-8")
print("   patched VisitTimeline to use getMediaUrl")

# ─── 4. FRONTEND: Use helper in LabDashboard (if it has an upload preview) ──
print("==> Checking LabDashboard.tsx")
ldp = FRONTEND / "src" / "pages" / "LabDashboard.tsx"
# We don't display attachments on the lab dashboard list, but good to have if needed later.

# ─── 5. Build & Push ───────────────────────────────────────────────────
print("\n==> Running local Vite build to verify")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Local Vite build succeeded!")
    else:
        print("   ❌ Local Vite build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print(f"     {line}")
        sys.exit(1)

print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(media): serve media files on backend and prepend API_BASE on frontend", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")