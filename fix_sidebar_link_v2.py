#!/usr/bin/env python3
"""
fix_sidebar_link_v2.py
1. Finds the file containing the '/staff' route.
2. Duplicates the exact line/block used for Staff.
3. Modifies it for 'Communication' and '/communication-settings'.
4. Builds and pushes.
"""
import subprocess, sys, shutil, os, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"

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

print("==> Searching for the Staff link definition...")
sidebar_patched = False

# Scan all TS/TSX files for the staff route
for p in SRC.glob("**/*.tsx"):
    lines = p.read_text(encoding="utf-8").splitlines()
    
    for i, line in enumerate(lines):
        if '"/staff"' in line or "'/staff'" in line:
            print(f"   Found '/staff' in {p.relative_to(FRONTEND)} at line {i+1}")
            
            # If it's a JSX link
            if "<Link" in line or "<NavLink" in line:
                # Copy the line and modify it
                new_line = line.replace('/staff', '/communication-settings')
                new_line = new_line.replace('Staff', 'Communication')
                # Replace the icon (assume it's a component like <Users />)
                new_line = re.sub(r'<([A-Z][a-zA-Z0-9]*)\s', r'<MessageSquare ', new_line)
                new_line = re.sub(r'<([A-Z][a-zA-Z0-9]*)/>', r'<MessageSquare />', new_line)
                
                lines.insert(i + 1, new_line)
            
            # If it's an array of objects (e.g., { name: 'Staff', href: '/staff', icon: Users })
            elif "name:" in line or "label:" in line or "href:" in line:
                new_line = line.replace('/staff', '/communication-settings')
                new_line = new_line.replace("'Staff'", "'Communication'")
                new_line = new_line.replace('"Staff"', '"Communication"')
                # Replace icon reference
                new_line = re.sub(r'icon:\s*([A-Z][a-zA-Z0-9]*)', r'icon: MessageSquare', new_line)
                new_line = re.sub(r'icon=\{([A-Z][a-zA-Z0-9]*)\}', r'icon={MessageSquare}', new_line)
                
                lines.insert(i + 1, new_line)
            
            else:
                print("   [WARN] Found '/staff' but could not determine format. Skipping.")
                continue
                
            # Ensure MessageSquare is imported from lucide-react
            txt = "\n".join(lines)
            if "MessageSquare" not in txt.split("export default")[0]:
                if "from 'lucide-react'" in txt:
                    txt = re.sub(r"import \{([^}]+)\} from 'lucide-react';", r"import {\1, MessageSquare} from 'lucide-react';", txt)
                elif 'from "lucide-react"' in txt:
                    txt = re.sub(r'import \{([^}]+)\} from "lucide-react";', r'import {\1, MessageSquare} from "lucide-react";', txt)
                    
            p.write_text(txt, encoding="utf-8")
            print(f"   ✓ Injected Communication link into {p.name}")
            sidebar_patched = True
            break
            
    if sidebar_patched:
        break

if not sidebar_patched:
    print("   [WARN] Could not find the Sidebar file automatically.")
    print("   Please manually add this to your ADMIN section:")
    print('   <Link to="/communication-settings"> <MessageSquare /> Communication </Link>')
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
    subprocess.run(["git", "commit", "-m", "fix(ui): add communication link to sidebar"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print("\n✅ Pushed successfully.")
else:
    print("   (nothing to commit)")

print("\nNEXT STEPS:")
print("  1. Deploy the frontend on Render.")
print("  2. You will now see 'Communication' in your sidebar.")