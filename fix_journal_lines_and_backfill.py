#!/usr/bin/env python3
"""
fix_journal_lines_and_backfill.py
  - Makes the backfill command crash-proof.
  - Adds it to render.yaml startup so it fixes production.
  - Forces the AccountingDashboard UI to show expandable lines.
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

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, capture_output=True, text=True)

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

# ─── 1. BACKEND: Make backfill command crash-proof ─────────────────────
print("==> Overwriting accounting/management/commands/backfill_je.py")
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

        try:
            for tenant in Tenant.objects.all():
                with db_tenant_context(tenant):
                    # 1. Backfill Invoices
                    invoices = Invoice.all_objects.filter(tenant=tenant)
                    for inv in invoices:
                        # Delete existing empty JEs for this invoice
                        JournalEntry.all_objects.filter(
                            tenant=tenant, reference=inv.invoice_no
                        ).delete()

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
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Backfill failed: {e}"))
''')

# ─── 2. FRONTEND: Force AccountingDashboard UI update ──────────────────
print("==> Overwriting src/pages/AccountingDashboard.tsx")
DASHBOARD = '''\
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">General Ledger</h1>
        <p className="text-sm text-slate-500 mt-1">Review and approve journal entries. Click a row to see the Debits and Credits.</p>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3">Date</th>
              <th className="text-left px-4 py-3">Reference</th>
              <th className="text-left px-4 py-3">Description</th>
              <th className="text-left px-4 py-3">Total Amount</th>
              <th className="text-left px-4 py-3">Status</th>
              {isManager && <th className="text-right px-4 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y">
            {entries.data?.map((je: any) => {
              // Calculate total by summing the debits
              const total = je.lines?.reduce((sum: number, l: any) => sum + parseFloat(l.debit), 0) || 0;
              
              return (
                <>
                  <tr key={je.id} className="hover:bg-slate-50 cursor-pointer" onClick={() => setExpanded(expanded === je.id ? null : je.id)}>
                    <td className="px-4 py-3">{je.date}</td>
                    <td className="px-4 py-3 font-mono text-xs">{je.reference}</td>
                    <td className="px-4 py-3 text-slate-500">{je.description}</td>
                    <td className="px-4 py-3 font-bold text-slate-700">ZMW {total.toFixed(2)}</td>
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
                    <tr key={`${je.id}-lines`} className="bg-slate-50 border-b">
                      <td colSpan={isManager ? 6 : 5} className="px-4 py-4">
                        <div className="pl-8">
                          <h4 className="font-semibold text-slate-700 mb-2">Journal Lines</h4>
                          <table className="w-full text-xs bg-white border rounded">
                            <thead className="text-slate-500 border-b bg-slate-50">
                              <tr>
                                <th className="text-left px-3 py-2">Account</th>
                                <th className="text-right px-3 py-2">Debit (ZMW)</th>
                                <th className="text-right px-3 py-2">Credit (ZMW)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y">
                              {je.lines?.map((line: any) => (
                                <tr key={line.id}>
                                  <td className="px-3 py-2">{line.account_name}</td>
                                  <td className="px-3 py-2 text-right font-mono text-slate-700">{line.debit > 0 ? parseFloat(line.debit).toFixed(2) : "—"}</td>
                                  <td className="px-3 py-2 text-right font-mono text-slate-700">{line.credit > 0 ? parseFloat(line.credit).toFixed(2) : "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
'''
write_frontend("src/pages/AccountingDashboard.tsx", DASHBOARD)

# ─── 3. Update render.yaml to run backfill on boot ─────────────────────
print("\n==> Updating render.yaml to run backfill_je")
ry = ROOT / "render.yaml"
if ry.exists():
    y = ry.read_text(encoding="utf-8")
    old_cmd = "python manage.py migrate --noinput && python manage.py seed_coa && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
    new_cmd = "python manage.py migrate --noinput && python manage.py seed_coa && python manage.py backfill_je && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
    
    if old_cmd in y:
        y = y.replace(old_cmd, new_cmd)
        ry.write_text(y, encoding="utf-8")
        print("   added backfill_je to startCommand")
    elif "backfill_je" in y:
        print("   render.yaml already has backfill_je")

# ─── 4. Build & Push ───────────────────────────────────────────────────
print("\n==> Running local Vite build to verify")
import shutil
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
r = sh("git", "commit", "-m", "fix(accounting): backfill lines on startup and expandable ledger UI", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")