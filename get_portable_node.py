
#!/usr/bin/env python3
"""
get_portable_node.py -- download a portable Node.js and run the frontend scaffold.
"""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

NODE_VERSION = "22.11.0"
NODE_URL = f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-win-x64.zip"

HOME = Path.home()
DJANGO_ROOT = Path.cwd().parent          # C:\Users\Howardm\Documents\django
NODE_DIR     = DJANGO_ROOT / "nodejs"    # portable install location
NODE_ZIP     = DJANGO_ROOT / "node.zip"


def sh(*cmd, **kw):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def main() -> None:
    # ─── 1. Already there? ───────────────────────────────────────────
    node_bin = NODE_DIR / "node.exe"
    if node_bin.exists():
        print(f"==> Portable Node already present at {NODE_DIR}")
    else:
        # ─── 2. Download ─────────────────────────────────────────────
        if not NODE_ZIP.exists():
            print(f"==> Downloading Node v{NODE_VERSION} portable (~30 MB)")
            print(f"    from {NODE_URL}")
            urllib.request.urlretrieve(NODE_URL, NODE_ZIP)
            print(f"    saved {NODE_ZIP} ({NODE_ZIP.stat().st_size // 1_000_000} MB)")
        else:
            print(f"==> Reusing cached ZIP at {NODE_ZIP}")

        # ─── 3. Extract ──────────────────────────────────────────────
        print(f"==> Extracting to {DJANGO_ROOT}")
        with zipfile.ZipFile(NODE_ZIP) as z:
            z.extractall(DJANGO_ROOT)

        # Rename the versioned folder to a stable one
        extracted = DJANGO_ROOT / f"node-v{NODE_VERSION}-win-x64"
        if NODE_DIR.exists():
            raise SystemExit(f"{NODE_DIR} already exists but isn't a node install — "
                             f"delete it manually and re-run.")
        extracted.rename(NODE_DIR)
        print(f"    renamed {extracted.name} → nodejs")

    # ─── 4. Add to PATH for this process only ────────────────────────
    os.environ["PATH"] = str(NODE_DIR) + os.pathsep + os.environ.get("PATH", "")

    # ─── 5. Verify ───────────────────────────────────────────────────
    print("==> Verifying portable Node")
    sh("node", "--version")
    sh("npm", "--version")

    # ─── 6. Run the frontend scaffolder ──────────────────────────────
    print()
    print("==> Running create_frontend.py")
    sh(sys.executable, "create_frontend.py")

    # ─── 7. Give the user a copy-pasteable activation command ────────
    print()
    print("=" * 70)
    print("SUCCESS. Node is installed at:")
    print(f"    {NODE_DIR}")
    print()
    print("For THIS PowerShell session only, activate it with:")
    print(f"    $env:PATH = '{NODE_DIR};' + $env:PATH")
    print()
    print("For future sessions, either re-run the above line, OR add it")
    print("permanently to your user PATH (no admin needed):")
    print()
    print("    [Environment]::SetEnvironmentVariable(")
    print('        "PATH",')
    print(f'        "{NODE_DIR};" + [Environment]::GetEnvironmentVariable("PATH", "User"),')
    print('        "User"')
    print("    )")
    print("=" * 70)


if __name__ == "__main__":
    main()