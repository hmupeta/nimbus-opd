#!/usr/bin/env python3
"""
fix_sidebar_link.py
1. Finds the Sidebar file by looking for the "Staff" link.
2. Adds a 'Communication' link with the MessageSquare icon right below "Staff" (in the Admin section).
3. Builds and pushes.
"""
import subprocess, sys, shutil, os, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"

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

print("==> Searching for the Sidebar navigation file (looking for 'Staff' link)...")
sidebar_patched = False

# Search all TSX files for the Staff link (which is in the ADMIN section)
for p in FRONTEND.glob("src/**/*.tsx"):
    txt = p.read_text(encoding="utf-8")
    
    # Look for the Staff link
    match = re.search(r'(<(?:NavLink|Link)[^>]*to=["\']/staff["\'][^>]*>[\s\S]*?<\/(?:NavLink|Link)>)', txt)
    
    if match:
        print(f"   Found Staff link in {p.relative_to(FRONTEND)}")
        
        if "communication-settings" in txt:
            print("   Sidebar already has the Communication link.")
            sidebar_patched = True
            break

        original_link = match.group(1)
        
        # 1. Create the new link by copying the Staff link
        new_link = original_link.replace('to="/staff"', 'to="/communication-settings"')
        new_link = new_link.replace("to='/staff'", "to='/communication-settings'")
        
        # 2. Swap the text "Staff" for "Communication"
        new_link = new_link.replace("Staff", "Communication")
        
        # 3. Swap the icon (find the first icon component and replace it with MessageSquare)
        icon_match = re.search(r'<([A-Z][a-zA-Z0-9]*)\s', new_link)
        if icon_match:
            icon_name = icon_match.group(1)
            new_link = new_link.replace(f"<{icon_name}", "<MessageSquare")
            
        # 4. Inject the new link right below the Staff link
        txt = txt.replace(original_link, original_link + "\n          " + new_link)
        
        # 5. Ensure MessageSquare is imported
        if "MessageSquare" not in txt.split("export default")[0]: # Check top imports
            if "from 'lucide-react'" in txt:
                txt = re.sub(r"import \{([^}]+)\} from 'lucide-react';", r"import {\1, MessageSquare} from 'lucide-react';", txt)
            elif 'from "lucide-react"' in txt:
                txt = re.sub(r'import \{([^}]+)\} from "lucide-react";', r'import {\1, MessageSquare} from "lucide-react";', txt)
                
        p.write_text(txt, encoding="utf-8")
        print(f"   ✓ Injected Communication link into {p.name} under ADMIN section")
        sidebar_patched = True
        break

if not sidebar_patched:
    print("   [WARN] Could not find the Sidebar file automatically.")
    print("   Please manually add this to your ADMIN section in the Sidebar:")
    print('   <NavLink to="/communication-settings"> <MessageSquare /> Communication </NavLink>')
    sys.exit(1)

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
    subprocess.run(["git", "commit", "-m", "fix(ui): add communication settings link to admin section"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print("\n✅ Pushed successfully.")
else:
    print("   (nothing to commit)")

print("\nNEXT STEPS:")
print("  1. Deploy the frontend on Render.")
print("  2. You will now see 'Communication' right under 'Staff' in the ADMINISTRATION section.")