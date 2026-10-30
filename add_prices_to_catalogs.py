#!/usr/bin/env python3
"""
add_prices_to_catalogs.py
  - Shows base_price in Doctor's dropdowns.
  - Adds a price input for Custom items.
  - Updates backend to save the custom price to the catalog for future use.
"""
from __future__ import annotations
import os
import re
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
FRONTEND = ROOT / "frontend"
VP = ROOT / "api" / "views.py"
VT = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, capture_output=True, text=True)

# ─── 1. BACKEND: Update order_lab, order_radiology, prescribe ──────────
print("==> Patching api/views.py (Backend Pricing)")
v = VP.read_text(encoding="utf-8")

# 1a. Lab
old_lab = '''        else:
            # Create custom test on the fly
            test, _ = LabTest.objects.get_or_create(
                tenant=visit.tenant,
                name=custom_test_name,
                defaults={"code": custom_test_name[:10].upper().replace(" ", ""), "base_price": Decimal("0.00")}
            )'''
new_lab = '''        else:
            # Create custom test on the fly with provided price
            custom_price = request.data.get("custom_price", "0.00")
            test, _ = LabTest.objects.get_or_create(
                tenant=visit.tenant,
                name=custom_test_name,
                defaults={
                    "code": custom_test_name[:10].upper().replace(" ", ""),
                    "base_price": Decimal(str(custom_price))
                }
            )'''
if old_lab in v:
    v = v.replace(old_lab, new_lab)

# 1b. Radiology
old_rad = '''        elif custom_modality and custom_body_part:
            modality = custom_modality
            body_part = custom_body_part
            code = f"{modality}-{body_part}"
            desc = f"{modality} {body_part}"
            price = Decimal("0.00")'''
new_rad = '''        elif custom_modality and custom_body_part:
            custom_price = request.data.get("custom_price", "0.00")
            modality = custom_modality
            body_part = custom_body_part
            code = f"{modality}-{body_part}"[:32].upper().replace(" ", "-")
            desc = f"{modality} {body_part}"
            price = Decimal(str(custom_price))
            # Save to catalog for next time
            RadiologyExam.objects.get_or_create(
                tenant=visit.tenant, code=code,
                defaults={"name": desc, "modality": modality, "body_part": body_part, "base_price": price}
            )'''
if old_rad in v:
    v = v.replace(old_rad, new_rad)

# 1c. Pharmacy
old_med = '''        elif custom_med_name:
            med, _ = Medicine.objects.get_or_create(
                tenant=visit.tenant, name=custom_med_name,
                defaults={"code": custom_med_name[:10].upper().replace(" ", ""), "base_price": Decimal("0.00")}
            )'''
new_med = '''        elif custom_med_name:
            custom_price = request.data.get("custom_price", "0.00")
            med, _ = Medicine.objects.get_or_create(
                tenant=visit.tenant, name=custom_med_name,
                defaults={
                    "code": custom_med_name[:10].upper().replace(" ", ""),
                    "base_price": Decimal(str(custom_price))
                }
            )'''
if old_med in v:
    v = v.replace(old_med, new_med)

VP.write_text(v, encoding="utf-8")
print("   patched backend custom price logic")

# ─── 2. FRONTEND: Update VisitTimeline.tsx ─────────────────────────────
print("==> Patching VisitTimeline.tsx (UI Pricing)")
c = VT.read_text(encoding="utf-8")

# 2a. Lab Dropdown & Custom Input
c = c.replace(
    '<option key={l.id} value={l.id}>{l.name} ({l.code})</option>',
    '<option key={l.id} value={l.id}>{l.name} - ZMW {l.base_price}</option>'
)
old_lab_custom = '''                  {customTest && (
                    <input name="custom_test_name" required placeholder="Enter test name (e.g. Malaria RDT)" className="w-full border rounded px-2 py-1 text-xs" />
                  )}'''
new_lab_custom = '''                  {customTest && (
                    <div className="space-y-1">
                      <input name="custom_test_name" required placeholder="Enter test name (e.g. Malaria RDT)" className="w-full border rounded px-2 py-1 text-xs" />
                      <input type="number" step="0.01" name="custom_price" required placeholder="Price (ZMW)" className="w-full border rounded px-2 py-1 text-xs" />
                    </div>
                  )}'''
c = c.replace(old_lab_custom, new_lab_custom)
c = c.replace(
    'orderLab.mutate({ custom_test_name: fd.get("custom_test_name") });',
    'orderLab.mutate({ custom_test_name: fd.get("custom_test_name"), custom_price: fd.get("custom_price") });'
)

# 2b. Radiology Dropdown & Custom Input
c = c.replace(
    '<option key={r.id} value={r.id}>{r.name} ({r.modality} {r.body_part})</option>',
    '<option key={r.id} value={r.id}>{r.name} - ZMW {r.base_price}</option>'
)
old_rad_custom = '''                  {customRad && (
                    <div className="grid grid-cols-2 gap-1">
                      <input name="custom_modality" placeholder="Modality (X-ray, CT...)" required className="w-full border rounded px-2 py-1 text-xs" />
                      <input name="custom_body_part" placeholder="Body Part" required className="w-full border rounded px-2 py-1 text-xs" />
                    </div>
                  )}'''
new_rad_custom = '''                  {customRad && (
                    <div className="space-y-1">
                      <div className="grid grid-cols-2 gap-1">
                        <input name="custom_modality" placeholder="Modality (X-ray, CT...)" required className="w-full border rounded px-2 py-1 text-xs" />
                        <input name="custom_body_part" placeholder="Body Part" required className="w-full border rounded px-2 py-1 text-xs" />
                      </div>
                      <input type="number" step="0.01" name="custom_price" required placeholder="Price (ZMW)" className="w-full border rounded px-2 py-1 text-xs" />
                    </div>
                  )}'''
c = c.replace(old_rad_custom, new_rad_custom)
c = c.replace(
    'orderRadiology.mutate({ custom_modality: fd.get("custom_modality"), custom_body_part: fd.get("custom_body_part"), notes: fd.get("notes") });',
    'orderRadiology.mutate({ custom_modality: fd.get("custom_modality"), custom_body_part: fd.get("custom_body_part"), custom_price: fd.get("custom_price"), notes: fd.get("notes") });'
)

# 2c. Pharmacy Dropdown & Custom Input
c = c.replace(
    '<option key={m.id} value={m.id}>{m.name} {m.strength}</option>',
    '<option key={m.id} value={m.id}>{m.name} {m.strength} - ZMW {m.base_price}</option>'
)
old_med_custom = '''                  {customMed && (
                    <input name="custom_medicine_name" placeholder="Enter medicine name" required className="w-full border rounded px-2 py-1 text-xs" />
                  )}'''
new_med_custom = '''                  {customMed && (
                    <div className="space-y-1">
                      <input name="custom_medicine_name" placeholder="Enter medicine name" required className="w-full border rounded px-2 py-1 text-xs" />
                      <input type="number" step="0.01" name="custom_price" required placeholder="Price (ZMW)" className="w-full border rounded px-2 py-1 text-xs" />
                    </div>
                  )}'''
c = c.replace(old_med_custom, new_med_custom)
c = c.replace(
    'payload.custom_medicine_name = fd.get("custom_medicine_name");',
    'payload.custom_medicine_name = fd.get("custom_medicine_name");\n                    payload.custom_price = fd.get("custom_price");'
)

VT.write_text(c, encoding="utf-8")
print("   patched frontend custom price inputs and dropdowns")

# ─── 3. Build & Push ───────────────────────────────────────────────────
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
r = sh("git", "commit", "-m", "feat(clinical): show prices in dropdowns and allow custom item pricing", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")