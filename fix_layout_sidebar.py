#!/usr/bin/env python3
"""
fix_layout_sidebar.py
1. Directly targets src/components/Layout.tsx.
2. Extracts the multi-line JSX block for the Staff link.
3. Clones it for Communication.
4. Builds and pushes.
"""
import subprocess, sys, shutil, os, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

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

layout_path = SRC / "components" / "Layout.tsx"
if not layout_path.exists():
    sys.exit("Could not find src/components/Layout.tsx")

print(f"==> Reading {layout_path.relative_to(FRONTEND)}...")
txt = layout_path.read_text(encoding="utf-8")

if "communication-settings" in txt:
    print("   Sidebar already has the Communication link.")
    sys.exit(0)

# Regex to match a multi-line <Link> or <NavLink> block that contains /staff
# It looks for the opening tag, captures everything inside, and the closing tag.
pattern = r'(<(?:(?:Nav)?Link)[^>]*?to=["\']/staff["\'][\s\S]*?<\/(?:Nav)?Link>)'
match = re.search(pattern, txt)

if not match:
    # Try matching a self-closing custom component like <SidebarItem to="/staff" />
    pattern_custom = r'(<[A-Z][a-zA-Z0-9]*[^>]*?to=["\']/staff["\'][^>]*?\/>)'
    match = re.search(pattern_custom, txt)

if match:
    print("   Found Staff link block.")
    original_block = match.group(1)
    
    # Create the new block
    new_block = original_block.replace('/staff', '/communication-settings')
    new_block = new_block.replace('Staff', 'Communication')
    
    # Try to replace the icon. Look for an icon component (capitalized) and swap to MessageSquare
    # This handles both <Icon /> and icon={Icon} formats
    new_block = re.sub(r'<([A-Z][a-zA-Z0-9]*)\s', r'<MessageSquare ', new_block)
    new_block = re.sub(r'<([A-Z][a-zA-Z0-9]*)/>', r'<MessageSquare/>', new_block)
    new_block = re.sub(r'icon=\{([A-Z][a-zA-Z0-9]*)\}', r'icon={MessageSquare}', new_block)
    
    # Inject the new block directly below the original block
    txt = txt.replace(original_block, original_block + "\n\n          " + new_block)
    
    # Ensure MessageSquare is imported
    if "MessageSquare" not in txt.split("export default")[0]:
        if "from 'lucide-react'" in txt:
            txt = re.sub(r"import \{([^}]+)\} from 'lucide-react';", r"import {\1, MessageSquare} from 'lucide-react';", txt)
        elif 'from "lucide-react"' in txt:
            txt = re.sub(r'import \{([^}]+)\} from "lucide-react";', r'import {\1, MessageSquare} from "lucide-react";', txt)
            
    layout_path.write_text(txt, encoding="utf-8")
    print("   ✓ Injected Communication link into Layout.tsx")
else:
    print("   [WARN] Could not find the Staff link block with regex.")
    print("   Please manually add this below Staff in Layout.tsx:")
    print('''
    <NavLink to="/communication-settings">
      <MessageSquare size={18} />
      <span>Communication</span>
    </NavLink>
    ''')
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
    subprocess.run(["git", "commit", "-m", "fix(ui): inject communication link directly into Layout.tsx"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print("\n✅ Pushed successfully.")
else:
    print("   (nothing to commit)")

print("\nNEXT STEPS:")
print("  1. Deploy the frontend on Render.")
print("  2. You will now see 'Communication' in the ADMINISTRATION section.")