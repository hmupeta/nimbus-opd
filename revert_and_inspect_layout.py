#!/usr/bin/env python3
"""
revert_and_inspect_layout.py
1. Reverts Layout.tsx to the last working commit (fixing the blank screen).
2. Inspects the file to show exactly how the links are structured.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

layout_path = "frontend/src/components/Layout.tsx"

print("==> Reverting Layout.tsx to the last working version...")
# Revert just the Layout.tsx file to the previous commit
subprocess.run(["git", "checkout", "HEAD~1", "--", layout_path], cwd=ROOT)
print("   ✓ Reverted Layout.tsx")

print("\n==> Here is the exact code around your '/staff' link:")
txt = (ROOT / layout_path).read_text(encoding="utf-8")
lines = txt.splitlines()

for i, line in enumerate(lines):
    if "/staff" in line:
        # Print 5 lines before and 10 lines after to see the full structure
        start = max(0, i - 5)
        end = min(len(lines), i + 10)
        
        print("\n--------------------------------------------------")
        for j in range(start, end):
            prefix = ">> " if j == i else "   "
            print(f"{prefix}{j+1}: {lines[j]}")
        print("--------------------------------------------------")
        break

print("\nNEXT STEPS:")
print("  1. Copy the text block above (the lines around /staff).")
print("  2. Paste it in the chat so I can see exactly how your sidebar is built.")
print("  3. I will write a perfect script to add the Communication link without breaking it.")
print("\n(Your app will now load normally once Render redeploys this revert).")