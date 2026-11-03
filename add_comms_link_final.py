#!/usr/bin/env python3
"""
add_comms_link_final.py
1. Pushes the reverted (working) Layout.tsx to fix the blank screen.
2. Safely adds the Communication <NavItem> using exact string matching.
3. Builds and pushes.
"""
import subprocess, sys, shutil, os
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
LAYOUT_PATH = FRONTEND / "src" / "components" / "Layout.tsx"

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

npm = npm_path()
if not npm:
    sys.exit("npm not found")

print("==> Reading Layout.tsx...")
txt = LAYOUT_PATH.read_text(encoding="utf-8")

if 'to="/communication-settings"' in txt:
    print("   Communication link already exists!")
else:
    # 1. Inject the new NavItem safely by string replacement
    target_line = '<NavItem to="/staff" icon={UserCog} label="Staff" roles={["admin"]} />'
    new_line = '<NavItem to="/communication-settings" icon={MessageSquare} label="Communication" roles={["admin"]} />'
    
    if target_line in txt:
        # Look at the indentation of the target line and match it
        for line in txt.splitlines():
            if target_line in line:
                indent = line[:len(line) - len(line.lstrip())]
                break
        
        txt = txt.replace(target_line, target_line + f"\n{indent}{new_line}")
        print("   ✓ Successfully injected Communication link.")
    else:
        print("   [WARN] Could not find the exact Staff NavItem line. It may have changed.")

    # 2. Ensure MessageSquare is imported
    if "MessageSquare" not in txt.split("export default")[0]:
        import re
        # Try to add it to the lucide-react import
        if "from 'lucide-react'" in txt:
            txt = re.sub(r"import \{([^}]+)\} from 'lucide-react';", r"import {\1, MessageSquare} from 'lucide-react';", txt)
        elif 'from "lucide-react"' in txt:
            txt = re.sub(r'import \{([^}]+)\} from "lucide-react";', r'import {\1, MessageSquare} from "lucide-react";', txt)
        print("   ✓ Added MessageSquare import.")

    LAYOUT_PATH.write_text(txt, encoding="utf-8")

# ═════════════════════════════════════════════════════════════════════
# Build and Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running Vite build...")
env = os.environ.copy()
env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)

if r.returncode == 0:
    print("   ✓ Build succeeded!")
else:
    print("   ❌ Build failed:")
    for line in (r.stdout + r.stderr).splitlines()[-15:]:
        print("     " + line)
    sys.exit(1)

print("\n==> Committing and pushing...")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()

if status:
    subprocess.run(["git", "commit", "-m", "fix(ui): restore layout and safely add communication nav link"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print("\n✅ Pushed successfully.")
else:
    print("   (nothing to commit)")

print("\nNEXT STEPS:")
print("  1. Deploy the frontend on Render.")
print("  2. The blank screen will be fixed.")
print("  3. 'Communication' will appear in the ADMINISTRATION section.")