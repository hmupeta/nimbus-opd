#!/usr/bin/env python3
"""
add_render_rewrite.py
Adds an SPA rewrite rule to render.yaml so page refreshes don't 404.
"""
import sys
from pathlib import Path

ROOT = Path.cwd()
yaml_file = ROOT / "render.yaml"

if not yaml_file.exists():
    print("No render.yaml found. Please use the Render Dashboard method described above.")
    sys.exit(0)

content = yaml_file.read_text(encoding="utf-8")

if "routes:" not in content:
    # If no routes exist, add the routes block to the service
    # (Assuming standard static site configuration)
    print("Adding SPA rewrite rule to render.yaml...")
    # A simple heuristic to find the static site block and append routes
    if "type: web" in content or "type: static" in content:
        # This is a bit fragile without a YAML parser, but works for simple files
        lines = content.splitlines()
        new_lines = []
        in_frontend = False
        for line in lines:
            new_lines.append(line)
            if "name: nimbus-frontend" in line or "name: frontend" in line:
                in_frontend = True
        
        # Add routes block before the next service or at the end
        if in_frontend:
            new_lines.append("    routes:")
            new_lines.append("      - type: rewrite")
            new_lines.append("        source: /*")
            new_lines.append("        destination: /index.html")
            yaml_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            print("✅ Added SPA rewrite rule to render.yaml")
            print("   Commit and push this change, then redeploy on Render.")
        else:
            print("Could not automatically locate the frontend service in render.yaml. Please use the Dashboard method.")
    else:
        print("render.yaml found but it doesn't look like a standard service definition. Please use the Dashboard method.")
else:
    print("Routes already exist in render.yaml. Please check them manually or use the Dashboard method.")