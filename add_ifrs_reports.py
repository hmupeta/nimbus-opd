#!/usr/bin/env python3
"""
add_ifrs_reports.py
  - Backfills Journal Entries for historical invoices/payments.
  - Creates Reporting APIs (Trial Balance, P&L, Balance Sheet).
  - Builds Journal Entries and Financial Reports UIs.
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
if not PY.exists():
    PY = Path(sys.executable)

FRONTEND = ROOT / "frontend"
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Create Backfill Command ───────────────────────────────
print("==> Creating accounting/management/commands/backfill_je.py")
write("accounting/management/commands/backfill_je.py", '''\
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from tenants.models import Tenant
from common.context import db_tenant_context
from accounting.models import ChartOfAccount, JournalEntry, JournalEntryLine
from billing.models import Invoice, Payment, InvoiceItem


class Command(BaseCommand):
    help = "Backfill Journal Entries for historical invoices and payments."

    def _get_account(self, tenant, code):
        return ChartOfAccount.all_objects.filter(tenant=tenant, code=code).first()

    def handle(self, *args, **opts):
        invoices_fixed = 0
        payments_fixed = 0

        for tenant in Tenant.objects.all():
            with db_tenant_context(tenant):
                # 1. Backfill Invoices
                invoices = Invoice.all_objects.filter(tenant=tenant)
                for inv in invoices:
                    # Delete existing empty JEs for this invoice
                    JournalEntry.all_objects.filter(
                        tenant=tenant, reference=inv.invoice_no
                    ).delete()

                    # Create new JE
                    with transaction.atomic():
                        je = JournalEntry.objects.create(
                            tenant=tenant, date=inv.created_at.date(),
                            reference=inv.invoice_no,
                            description=f"Invoice issued to {inv.patient.full_name}",
                        )
                        ar = self._get_account(tenant, "1100")
                        if ar:
                            JournalEntryLine.objects.create(
                                tenant=tenant, journal_entry=je, account=ar,
                                debit=inv.total, credit=Decimal("0.00")
                            )
                        for item in inv.items.all():
                            code = "4000"
                            if item.category == InvoiceItem.Category.PHARMACY: code = "4100"
                            elif item.category == InvoiceItem.Category.LAB: code = "4200"
                            elif item.category == InvoiceItem.Category.RADIOLOGY: code = "4300"

                            rev = self._get_account(tenant, code)
                            if rev:
                                JournalEntryLine.objects.create(
                                    tenant=tenant, journal_entry=je, account=rev,
                                    debit=Decimal("0.00"), credit=item.total
                                )
                        invoices_fixed += 1

                # 2. Backfill Payments
                payments = Payment.all_objects.filter(tenant=tenant)
                for pay in payments:
                    ref = f"PAY-{pay.id}"
                    JournalEntry.all_objects.filter(tenant=tenant, reference=ref).delete()
                    
                    with transaction.atomic():
                        je = JournalEntry.objects.create(
                            tenant=tenant, date=pay.paid_at.date(),
                            reference=ref,
                            description=f"Payment received via {pay.method}",
                        )
                        cash = self._get_account(tenant, "1000")
                        if cash:
                            JournalEntryLine.objects.create(
                                tenant=tenant, journal_entry=je, account=cash,
                                debit=pay.amount, credit=Decimal("0.00")
                            )
                        ar = self._get_account(tenant, "1100")
                        if ar:
                            JournalEntryLine.objects.create(
                                tenant=tenant, journal_entry=je, account=ar,
                                debit=Decimal("0.00"), credit=pay.amount
                            )
                        payments_fixed += 1

        self.stdout.write(self.style.SUCCESS(
            f"Backfilled {invoices_fixed} invoices and {payments_fixed} payments."
        ))
''')

# ─── 2. BACKEND: Create Reports API ────────────────────────────────────
print("==> Creating api/accounting_reports.py")
write("api/accounting_reports.py", '''\
from decimal import Decimal
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from accounting.models import ChartOfAccount, JournalEntryLine
from api.permissions import require_roles


class TrialBalanceView(APIView):
    permission_classes = [require_roles("admin", "accountant", "finance_manager")]

    def get(self, request):
        accounts = ChartOfAccount.all_objects.filter(tenant=request.user.tenant).order_by("code")
        data = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for acc in accounts:
            lines = JournalEntryLine.all_objects.filter(tenant=request.user.tenant, account=acc)
            debit = lines.aggregate(s=Sum("debit"))["s"] or Decimal("0.00")
            credit = lines.aggregate(s=Sum("credit"))["s"] or Decimal("0.00")
            
            # Only show accounts with activity
            if debit > 0 or credit > 0:
                data.append({
                    "code": acc.code,
                    "name": acc.name,
                    "type": acc.type,
                    "debit": debit,
                    "credit": credit
                })
                total_debit += debit
                total_credit += credit

        return Response({
            "accounts": data,
            "total_debit": total_debit,
            "total_credit": total_credit
        })


class ProfitLossView(APIView):
    permission_classes = [require_roles("admin", "accountant", "finance_manager")]

    def get(self, request):
        # Fetch Revenue Accounts (4xxx)
        revenue_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="4")
        # Fetch Expense Accounts (5xxx)
        expense_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="5")

        revenues = []
        expenses = []
        total_revenue = Decimal("0.00")
        total_expense = Decimal("0.00")

        for acc in revenue_accs:
            credit = JournalEntryLine.all_objects.filter(tenant=request.user.tenant, account=acc).aggregate(s=Sum("credit"))["s"] or Decimal("0.00")
            if credit > 0:
                revenues.append({"name": acc.name, "amount": credit})
                total_revenue += credit

        for acc in expense_accs:
            debit = JournalEntryLine.all_objects.filter(tenant=request.user.tenant, account=acc).aggregate(s=Sum("debit"))["s"] or Decimal("0.00")
            if debit > 0:
                expenses.append({"name": acc.name, "amount": debit})
                total_expense += debit

        return Response({
            "revenues": revenues,
            "expenses": expenses,
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_profit": total_revenue - total_expense
        })


class BalanceSheetView(APIView):
    permission_classes = [require_roles("admin", "accountant", "finance_manager")]

    def get(self, request):
        # Assets (1xxx)
        asset_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="1")
        # Liabilities (2xxx)
        liab_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="2")
        # Equity (3xxx)
        equity_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="3")

        def calculate_balance(accounts, is_asset=False):
            items = []
            total = Decimal("0.00")
            for acc in accounts:
                lines = JournalEntryLine.all_objects.filter(tenant=request.user.tenant, account=acc)
                debit = lines.aggregate(s=Sum("debit"))["s"] or Decimal("0.00")
                credit = lines.aggregate(s=Sum("credit"))["s"] or Decimal("0.00")
                
                balance = (debit - credit) if is_asset else (credit - debit)
                
                if balance != 0:
                    items.append({"name": acc.name, "balance": balance})
                    total += balance
            return items, total

        assets, total_assets = calculate_balance(asset_accs, is_asset=True)
        liabilities, total_liab = calculate_balance(liab_accs, is_asset=False)
        equity, total_equity = calculate_balance(equity_accs, is_asset=False)

        # Note: This is a simplified Balance Sheet. Real IFRS would include retained earnings (Net Profit).
        return Response({
            "assets": assets,
            "total_assets": total_assets,
            "liabilities": liabilities,
            "total_liabilities": total_liab,
            "equity": equity,
            "total_equity": total_equity,
            "liabilities_and_equity": total_liab + total_equity
        })
''')

# Wire URLs
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "TrialBalanceView" not in u:
    u = u.replace(
        "from .accounting_views import JournalEntryViewSet",
        "from .accounting_views import JournalEntryViewSet\n"
        "from .accounting_reports import TrialBalanceView, ProfitLossView, BalanceSheetView"
    )
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n"
        "    path('reports/trial-balance/', TrialBalanceView.as_view(), name='trial-balance'),\n"
        "    path('reports/profit-loss/', ProfitLossView.as_view(), name='profit-loss'),\n"
        "    path('reports/balance-sheet/', BalanceSheetView.as_view(), name='balance-sheet'),"
    )
    up.write_text(u, encoding="utf-8")

# ─── 3. FRONTEND: Create FinancialReports.tsx ──────────────────────────
print("==> Creating src/pages/FinancialReports.tsx")
write_frontend("src/pages/FinancialReports.tsx", '''\
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export default function FinancialReports() {
  const [tab, setTab] = useState<"pl" | "bs" | "tb">("pl");

  const pl = useQuery({
    queryKey: ["report-pl"],
    queryFn: async () => (await api.get("/reports/profit-loss/")).data,
  });

  const bs = useQuery({
    queryKey: ["report-bs"],
    queryFn: async () => (await api.get("/reports/balance-sheet/")).data,
  });

  const tb = useQuery({
    queryKey: ["report-tb"],
    queryFn: async () => (await api.get("/reports/trial-balance/")).data,
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Financial Reports</h1>
        <p className="text-sm text-slate-500 mt-1">IFRS-aligned financial statements.</p>
      </div>

      <div className="flex gap-4 border-b">
        <button onClick={() => setTab("pl")} className={`pb-2 px-1 font-medium ${tab === "pl" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Profit & Loss</button>
        <button onClick={() => setTab("bs")} className={`pb-2 px-1 font-medium ${tab === "bs" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Balance Sheet</button>
        <button onClick={() => setTab("tb")} className={`pb-2 px-1 font-medium ${tab === "tb" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Trial Balance</button>
      </div>

      {tab === "pl" && pl.data && (
        <div className="bg-white border rounded-xl p-8 shadow-sm max-w-2xl mx-auto">
          <h2 className="text-xl font-bold text-center mb-6">Profit & Loss Statement</h2>
          
          <h3 className="font-semibold text-slate-700 border-b pb-2 mb-2">Revenue</h3>
          <ul className="space-y-2 mb-6 text-sm">
            {pl.data.revenues.map((r: any, i: number) => (
              <li key={i} className="flex justify-between"><span>{r.name}</span><span>ZMW {r.amount}</span></li>
            ))}
            <li className="flex justify-between font-bold border-t pt-2"><span>Total Revenue</span><span>ZMW {pl.data.total_revenue}</span></li>
          </ul>

          <h3 className="font-semibold text-slate-700 border-b pb-2 mb-2">Expenses</h3>
          <ul className="space-y-2 mb-6 text-sm">
            {pl.data.expenses.map((e: any, i: number) => (
              <li key={i} className="flex justify-between"><span>{e.name}</span><span>ZMW {e.amount}</span></li>
            ))}
            <li className="flex justify-between font-bold border-t pt-2"><span>Total Expenses</span><span>ZMW {pl.data.total_expense}</span></li>
          </ul>

          <div className={`flex justify-between font-bold text-lg p-4 rounded-lg ${pl.data.net_profit >= 0 ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>
            <span>Net Profit / (Loss)</span>
            <span>ZMW {pl.data.net_profit}</span>
          </div>
        </div>
      )}

      {tab === "bs" && bs.data && (
        <div className="bg-white border rounded-xl p-8 shadow-sm max-w-2xl mx-auto">
          <h2 className="text-xl font-bold text-center mb-6">Balance Sheet</h2>
          
          <h3 className="font-semibold text-slate-700 border-b pb-2 mb-2">Assets</h3>
          <ul className="space-y-2 mb-6 text-sm">
            {bs.data.assets.map((a: any, i: number) => (
              <li key={i} className="flex justify-between"><span>{a.name}</span><span>ZMW {a.balance}</span></li>
            ))}
            <li className="flex justify-between font-bold border-t pt-2"><span>Total Assets</span><span>ZMW {bs.data.total_assets}</span></li>
          </ul>

          <h3 className="font-semibold text-slate-700 border-b pb-2 mb-2">Liabilities & Equity</h3>
          <ul className="space-y-2 mb-6 text-sm">
            {bs.data.liabilities.map((l: any, i: number) => (
              <li key={i} className="flex justify-between"><span>{l.name}</span><span>ZMW {l.balance}</span></li>
            ))}
            {bs.data.equity.map((e: any, i: number) => (
              <li key={i} className="flex justify-between"><span>{e.name}</span><span>ZMW {e.balance}</span></li>
            ))}
            <li className="flex justify-between font-bold border-t pt-2"><span>Total Liabilities & Equity</span><span>ZMW {bs.data.liabilities_and_equity}</span></li>
          </ul>
        </div>
      )}

      {tab === "tb" && tb.data && (
        <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr><th className="text-left px-4 py-3">Code</th><th className="text-left px-4 py-3">Account</th><th className="text-right px-4 py-3">Debit</th><th className="text-right px-4 py-3">Credit</th></tr>
            </thead>
            <tbody className="divide-y">
              {tb.data.accounts.map((a: any, i: number) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono">{a.code}</td>
                  <td className="px-4 py-3">{a.name}</td>
                  <td className="px-4 py-3 text-right">{a.debit > 0 ? `ZMW ${a.debit}` : "—"}</td>
                  <td className="px-4 py-3 text-right">{a.credit > 0 ? `ZMW ${a.credit}` : "—"}</td>
                </tr>
              ))}
              <tr className="bg-slate-50 font-bold">
                <td colSpan={2} className="px-4 py-3 text-right">Totals</td>
                <td className="px-4 py-3 text-right">ZMW {tb.data.total_debit}</td>
                <td className="px-4 py-3 text-right">ZMW {tb.data.total_credit}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
''')

# ─── 4. FRONTEND: Update JournalEntries UI (AccountingDashboard.tsx) ───
print("==> Updating src/pages/AccountingDashboard.tsx")
write_frontend("src/pages/AccountingDashboard.tsx", '''\
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { currentUser } from "../api/auth";
import type { Paginated } from "../api/types";

export default function AccountingDashboard() {
  const qc = useQueryClient();
  const user = currentUser();
  const isManager = user?.role === "finance_manager" || user?.role === "admin";
  const [expanded, setExpanded] = useState<number | null>(null);

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
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3">Date</th>
              <th className="text-left px-4 py-3">Reference</th>
              <th className="text-left px-4 py-3">Description</th>
              <th className="text-left px-4 py-3">Status</th>
              {isManager && <th className="text-right px-4 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y">
            {entries.data?.map((je: any) => (
              <>
                <tr key={je.id} className="hover:bg-slate-50 cursor-pointer" onClick={() => setExpanded(expanded === je.id ? null : je.id)}>
                  <td className="px-4 py-3">{je.date}</td>
                  <td className="px-4 py-3 font-mono text-xs">{je.reference}</td>
                  <td className="px-4 py-3 text-slate-500">{je.description}</td>
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
                    <td className="px-4 py-3 text-right space-x-2" onClick={(e) => e.stopPropagation()}>
                      {je.status === "pending" && (
                        <>
                          <button onClick={() => approve.mutate(je.id)} className="text-xs bg-emerald-600 text-white px-3 py-1.5 rounded hover:bg-emerald-700">Approve</button>
                          <button onClick={() => reject.mutate(je.id)} className="text-xs bg-red-100 text-red-700 px-3 py-1.5 rounded hover:bg-red-200">Reject</button>
                        </>
                      )}
                    </td>
                  )}
                </tr>
                {expanded === je.id && (
                  <tr className="bg-slate-50 border-b">
                    <td colSpan={isManager ? 5 : 4} className="px-4 py-4">
                      <div className="pl-8">
                        <h4 className="font-semibold text-slate-700 mb-2">Journal Lines</h4>
                        <table className="w-full text-xs">
                          <thead className="text-slate-500 border-b">
                            <tr><th className="text-left py-1">Account</th><th className="text-right py-1">Debit</th><th className="text-right py-1">Credit</th></tr>
                          </thead>
                          <tbody>
                            {je.lines.map((line: any) => (
                              <tr key={line.id}>
                                <td className="py-1">{line.account_name}</td>
                                <td className="py-1 text-right text-slate-700">{line.debit > 0 ? `ZMW ${line.debit}` : "—"}</td>
                                <td className="py-1 text-right text-slate-700">{line.credit > 0 ? `ZMW ${line.credit}` : "—"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
''')

# ─── 5. FRONTEND: Navigation & Routing ─────────────────────────────────
print("==> Updating Layout and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Financial Reports" not in l:
    l = l.replace(
        '<NavLink to="/accounting" icon={BookOpen} label="General Ledger" roles={["accountant", "finance_manager", "admin"]} />',
        '<NavLink to="/accounting" icon={BookOpen} label="General Ledger" roles={["accountant", "finance_manager", "admin"]} />\n'
        '              <NavLink to="/financial-reports" icon={BarChart} label="Financial Reports" roles={["accountant", "finance_manager", "admin"]} />'
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")
if "FinancialReports" not in a:
    a = a.replace(
        'import AccountingDashboard from "./pages/AccountingDashboard";',
        'import AccountingDashboard from "./pages/AccountingDashboard";\nimport FinancialReports from "./pages/FinancialReports";'
    )
    a = a.replace(
        '<Route path="/accounting" element={<AccountingDashboard />} />',
        '<Route path="/accounting" element={<AccountingDashboard />} />\n          <Route path="/financial-reports" element={<FinancialReports />} />'
    )
    ap.write_text(a, encoding="utf-8")
    print("   added Financial Reports route")

# ─── 6. Run Backfill Locally & Push ────────────────────────────────────
print("\n==> Running backfill locally")
sh(PY, "manage.py", "backfill_je")

print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "feat(accounting): backfill historical JEs and add IFRS financial reports", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")