#!/usr/bin/env python3
"""
fix_lab_save_and_dashboard.py -- Fix tenant assignment in LabResult save,
                                 and restrict Dashboard access for Lab Techs.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
if not FRONTEND.exists():
    sys.exit(f"Frontend not found at {FRONTEND}.")


def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")


# ─── 1. BACKEND: Fix LabOrderViewSet.result ────────────────────────────
print("==> Patching api/views.py (LabResult tenant assignment)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_result = '''    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "lab")])
    def result(self, request, pk=None):
        lo = self.get_object()
        ser = LabResultSerializer(data={**request.data, "lab_order": lo.pk})
        ser.is_valid(raise_exception=True)
        ser.save(resulted_by=request.user)
        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        return Response(ser.data, status=status.HTTP_201_CREATED)'''

new_result = '''    @action(detail=True, methods=["post"],
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

if old_result in v:
    v = v.replace(old_result, new_result)
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py")
else:
    print("   [WARN] Could not find exact result action block.")

# ─── 2. FRONTEND: Update Dashboard to redirect Lab Techs ───────────────
print("==> Updating Dashboard.tsx to handle Lab Tech roles")
dp = FRONTEND / "src" / "pages" / "Dashboard.tsx"
d = dp.read_text(encoding="utf-8")

# Add redirect logic at the top of the component
if "Navigate" not in d:
    d = d.replace(
        'import { Link } from "react-router-dom";',
        'import { Link, Navigate } from "react-router-dom";\nimport { currentUser } from "../api/auth";'
    )
    
    d = d.replace(
        'export default function Dashboard() {\n  const summary = useQuery({',
        'export default function Dashboard() {\n  const user = currentUser();\n  if (user?.role === "lab") {\n    return <Navigate to="/lab" replace />;\n  }\n\n  const summary = useQuery({'
    )
    dp.write_text(d, encoding="utf-8")
    print("   patched src/pages/Dashboard.tsx")

print("==> Done. Restart the Django server and refresh your browser.")