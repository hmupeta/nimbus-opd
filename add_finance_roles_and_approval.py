#!/usr/bin/env python3
"""
add_finance_roles_and_approval.py
  - Adds accountant & finance_manager roles
  - Adds 'status' (Pending/Approved) to Journal Entries
  - Updates signals to create pending entries
  - Builds an Accounting UI for viewing and approving
  - Seeds accountant@demo.local and finance@demo.local
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

FRONTEND = ROOT / "frontend"

def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. Update User Roles ──────────────────────────────────────────────
print("==> Patching tenants/models.py (New Roles)")
tp = ROOT / "tenants" / "models.py"
t = tp.read_text(encoding="utf-8")

if '("accountant", "Accountant")' not in t:
    t = t.replace(
        '    ("pharmacist", "Pharmacist"),',
        '    ("pharmacist", "Pharmacist"),\n    ("accountant", "Accountant"),\n    ("finance_manager", "Finance Manager"),'
    )
    tp.write_text(t, encoding="utf-8")

# ─── 2. Update Accounting Models ───────────────────────────────────────
print("==> Patching accounting/models.py (Add Approval Workflow)")
am = ROOT / "accounting" / "models.py"
a = am.read_text(encoding="utf-8")

if "status = models.CharField" not in a:
    a = a.replace(
        'class JournalEntry(TenantAwareModel):\n    date = models.DateField()',
        '''class JournalEntry(TenantAwareModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey("tenants.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)'''
    )
    am.write_text(a, encoding="utf-8")

# ─── 3. Update Signals (Default to Pending) ────────────────────────────
print("==> Patching accounting/signals.py")
sm = ROOT / "accounting" / "signals.py"
s = sm.read_text(encoding="utf-8")
s = s.replace('reference=instance.invoice_no,', 'reference=instance.invoice_no,\n                status=JournalEntry.Status.PENDING,')
s = s.replace('reference=f"PAY-{instance.id}",', 'reference=f"PAY-{instance.id}",\n                status=JournalEntry.Status.PENDING,')
sm.write_text(s, encoding="utf-8")

# ─── 4. Accounting API ─────────────────────────────────────────────────
print("==> Creating api/accounting_views.py")
write("api/accounting_views.py", '''\
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounting.models import JournalEntry
from api.serializers import JournalEntrySerializer
from api.permissions import require_roles


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = JournalEntrySerializer
    permission_classes = [require_roles("admin", "accountant", "finance_manager")]

    def get_queryset(self):
        return JournalEntry.all_objects.all().order_by("-id")

    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "finance_manager")])
    def approve(self, request, pk=None):
        je = self.get_object()
        if je.status != JournalEntry.Status.PENDING:
            return Response({"detail": "Only pending entries can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        
        je.status = JournalEntry.Status.APPROVED
        je.approved_by = request.user
        je.approved_at = timezone.now()
        je.save()
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "finance_manager")])
    def reject(self, request, pk=None):
        je = self.get_object()
        if je.status != JournalEntry.Status.PENDING:
            return Response({"detail": "Only pending entries can be rejected."}, status=status.HTTP_400_BAD_REQUEST)
        
        je.status = JournalEntry.Status.REJECTED
        je.save()
        return Response({"status": "rejected"})
''')

# Add serializer
sp = ROOT / "api" / "serializers.py"
ser = sp.read_text(encoding="utf-8")
if "class JournalEntrySerializer" not in ser:
    ser += '''

from accounting.models import JournalEntry, JournalEntryLine

class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    class Meta:
        model = JournalEntryLine
        fields = ["id", "account", "account_name", "debit", "credit"]

class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalEntryLineSerializer(many=True, read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True, default="")
    
    class Meta:
        model = JournalEntry
        fields = ["id", "date", "reference", "description", "status", "approved_by_name", "approved_at", "lines"]
'''
    sp.write_text(ser, encoding="utf-8")

# Register route
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "JournalEntryViewSet" not in u:
    u = u.replace(
        "from .momo_views import MobileMoneyConfigViewSet",
        "from .momo_views import MobileMoneyConfigViewSet\nfrom .accounting_views import JournalEntryViewSet"
    )
    u = u.replace(
        'router.register("mobile-money-configs", MobileMoneyConfigViewSet, basename="momo")',
        'router.register("mobile-money-configs", MobileMoneyConfigViewSet, basename="momo")\n'
        'router.register("journal-entries", JournalEntryViewSet, basename="journal-entry")'
    )
    up.write_text(u, encoding="utf-8")

# ─── 5. Frontend UI ────────────────────────────────────────────────────
print("==> Creating Accounting UI")
write_frontend("src/pages/AccountingDashboard.tsx", '''\
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { currentUser } from "../api/auth";
import type { Paginated } from "../api/types";

export default function AccountingDashboard() {
  const qc = useQueryClient();
  const user = currentUser();
  const isManager = user?.role === "finance_manager" || user?.role === "admin";

  const entries = useQuery({
    queryKey: ["journal-entries"],
    queryFn: async () => (await api.get<Paginated<any>>("/journal-entries/")).data.results,
  });

  const approve = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/journal-entries/${id}/approve/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["journal-entries"] }),
  });

  const reject = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/journal-entries/${id}/reject/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["journal-entries"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">General Ledger</h1>
        <p className="text-sm text-slate-500 mt-1">Review and approve journal entries.</p>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Date</th>
              <th className="text-left px-4 py-3">Reference</th>
              <th className="text-left px-4 py-3">Description</th>
              <th className="text-left px-4 py-3">Debit Lines</th>
              <th className="text-left px-4 py-3">Credit Lines</th>
              <th className="text-left px-4 py-3">Status</th>
              {isManager && <th className="text-right px-4 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y">
            {entries.data?.map((je: any) => {
              const debit = je.lines.reduce((sum: number, l: any) => sum + parseFloat(l.debit), 0);
              const credit = je.lines.reduce((sum: number, l: any) => sum + parseFloat(l.credit), 0);
              return (
                <tr key={je.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">{je.date}</td>
                  <td className="px-4 py-3 font-mono text-xs">{je.reference}</td>
                  <td className="px-4 py-3 text-slate-500">{je.description}</td>
                  <td className="px-4 py-3 font-medium">ZMW {debit.toFixed(2)}</td>
                  <td className="px-4 py-3 font-medium">ZMW {credit.toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      je.status === "approved" ? "bg-emerald-100 text-emerald-700" :
                      je.status === "rejected" ? "bg-red-100 text-red-700" :
                      "bg-amber-100 text-amber-700"
                    }`}>
                      {je.status.toUpperCase()}
                    </span>
                  </td>
                  {isManager && (
                    <td className="px-4 py-3 text-right space-x-2">
                      {je.status === "pending" && (
                        <>
                          <button onClick={() => approve.mutate(je.id)} className="text-xs bg-emerald-600 text-white px-3 py-1.5 rounded hover:bg-emerald-700">Approve</button>
                          <button onClick={() => reject.mutate(je.id)} className="text-xs bg-red-100 text-red-700 px-3 py-1.5 rounded hover:bg-red-200">Reject</button>
                        </>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
''')

# Add to router and navigation
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Accounting" not in l:
    l = l.replace(
        '{isClinicalStaff && user?.role === "admin" && (',
        '{isClinicalStaff && (user?.role === "accountant" || user?.role === "finance_manager" || user?.role === "admin") && (\n              <NavLink to="/accounting" className={linkClass}>Accounting</NavLink>\n            )}\n\n            {isClinicalStaff && user?.role === "admin" && ('
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
app = ap.read_text(encoding="utf-8")
if "AccountingDashboard" not in app:
    app = app.replace(
        'import AuditTrail from "./pages/AuditTrail";',
        'import AuditTrail from "./pages/AuditTrail";\nimport AccountingDashboard from "./pages/AccountingDashboard";'
    )
    app = app.replace(
        '<Route path="/audit" element={<AuditTrail />} />',
        '<Route path="/audit" element={<AuditTrail />} />\n          <Route path="/accounting" element={<AccountingDashboard />} />'
    )
    ap.write_text(app, encoding="utf-8")

# ─── 6. Seed New Roles & Migrate ───────────────────────────────────────
print("==> Updating seed_demo.py for new users")
seed = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
sc = seed.read_text(encoding="utf-8")
if "accountant@demo.local" not in sc:
    sc = sc.replace(
        '            "pharmacy":  _make_user(tenant, "pharmacy@demo.local", "pharmacist",\n                                    "Peter", "Pharmacist", staff=True),',
        '            "pharmacy":  _make_user(tenant, "pharmacy@demo.local", "pharmacist",\n                                    "Peter", "Pharmacist", staff=True),\n            "accountant": _make_user(tenant, "accountant@demo.local", "accountant",\n                                    "Alice", "Accountant", staff=True),\n            "finance":    _make_user(tenant, "finance@demo.local", "finance_manager",\n                                    "Frank", "Manager", staff=True),'
    )
    seed.write_text(sc, encoding="utf-8")

print("==> makemigrations & migrate")
sh(PY, "manage.py", "makemigrations", "tenants", "accounting")
sh(PY, "manage.py", "migrate")

print("==> Done. Push to GitHub and redeploy.")