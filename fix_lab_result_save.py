#!/usr/bin/env python3
"""
fix_lab_result_save.py -- Bulletproof the LabResult action using update_or_create.
"""
from __future__ import annotations

import os
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

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


# ─── 1. Replace the result action in api/views.py ──────────────────────
print("==> Patching api/views.py (LabOrderViewSet.result)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_block = '''    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "lab")])
    def result(self, request, pk=None):
        lo = self.get_object()
        
        # Explicitly include tenant in the data to bypass any ContextVar clearing issues
        data = {**request.data, "lab_order": lo.pk, "tenant": lo.tenant_id}
        ser = LabResultSerializer(data=data)
        ser.is_valid(raise_exception=True)
        
        try:
            ser.save(resulted_by=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        return Response(ser.data, status=status.HTTP_201_CREATED)'''

new_block = '''    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "lab")])
    def result(self, request, pk=None):
        lo = self.get_object()
        
        # Use update_or_create to handle both new results and overrides safely
        result, created = LabResult.objects.update_or_create(
            lab_order=lo,
            defaults={
                "tenant": lo.tenant,
                "value_text": request.data.get("value_text"),
                "unit": request.data.get("unit", ""),
                "flag": request.data.get("flag", "normal"),
                "comment": request.data.get("comment", ""),
                "resulted_by": request.user,
            }
        )

        # Update the parent LabOrder status
        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        
        return Response(LabResultSerializer(result).data, status=status.HTTP_200_OK)'''

if old_block in v:
    v = v.replace(old_block, new_block)
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py")
else:
    print("   [WARN] Could not find exact result action block — checking for alternate version...")
    # Fallback if the user has a slightly different version from earlier patches
    import re
    # Replace from "@action(...)" def result up to the next @action or class
    pattern = re.compile(r"    @action\(detail=True, methods=\[\"post\"\],\s*permission_classes=\[require_roles\(\"admin\", \"lab\"\)\]\)\s*def result\(self, request, pk=None\):.*?(?=\n    @|\nclass|\Z)", re.DOTALL)
    if pattern.search(v):
        v = pattern.sub(new_block, v)
        vp.write_text(v, encoding="utf-8")
        print("   patched api/views.py (via regex)")
    else:
        print("   [ERROR] Could not patch. Please manually replace the result method in LabOrderViewSet.")

# ─── 2. Ensure the server checks run ───────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. You MUST restart the Django server for the changes to apply.")