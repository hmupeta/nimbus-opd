#!/usr/bin/env python3
"""
repair_invoice_view.py -- Safely fix the InvoiceViewSet class in api/views.py
"""
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# The exact, correct class definition
new_class = '''class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        # Use Invoice.objects (TenantManager) which handles tenant context automatically
        qs = Invoice.objects.all().order_by("-id")
        for field in ("status", "visit", "patient"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        inv = self.get_object()
        if inv.status != Invoice.Status.DRAFT:
            return Response({"detail": "Only drafts can be issued"},
                            status=status.HTTP_409_CONFLICT)
        inv.issued_at = timezone.now()
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["issued_at", "status"])
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        inv = self.get_object()
        inv.recalculate()
        return Response(InvoiceSerializer(inv).data)
'''

# Find the existing InvoiceViewSet class
# It starts with "class InvoiceViewSet(" and ends before the next "class " or EOF
pattern = re.compile(r"class InvoiceViewSet\(viewsets\.ModelViewSet\):.*?(?=\nclass |\Z)", re.DOTALL)

if pattern.search(v):
    v = pattern.sub(new_class.strip(), v, count=1)
    vp.write_text(v, encoding="utf-8")
    print("✅ Successfully rebuilt InvoiceViewSet.")
else:
    # If the previous script deleted it entirely, append it at the end
    print("⚠️ Could not find InvoiceViewSet, appending at the end of views.py")
    v += "\n\n" + new_class.strip()
    vp.write_text(v, encoding="utf-8")

# Verify it runs
import subprocess
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
print("==> Verifying manage.py check...")
subprocess.run([str(PY), "manage.py", "check"], check=True, cwd=ROOT)

print("\n==> Committing and pushing...")
subprocess.run(["git", "add", "api/views.py"], cwd=ROOT)
subprocess.run(["git", "commit", "-m", "fix(api): safely rebuild InvoiceViewSet after bad regex patch"], cwd=ROOT)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT)
print("✅ Pushed. You can now redeploy on Render.")