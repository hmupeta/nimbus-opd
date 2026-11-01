#!/usr/bin/env python3
"""
fix_cashflow_and_add_exports.py
  - Fixes the CashFlow import error.
  - Installs jspdf, jspdf-autotable, and xlsx in the frontend.
  - Adds Export to PDF/Excel buttons to all Financial Reports.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)

def sh(*cmd, check=True, cwd=ROOT):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=cwd)

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

# ─── 1. BACKEND: Fix the CashFlow import ───────────────────────────────
print("==> Patching api/accounting_reports.py")
rp = ROOT / "api" / "accounting_reports.py"
r = rp.read_text(encoding="utf-8")

old_import = "from billing.models import Payment, Expense, FixedAsset"
new_import = "from billing.models import Payment\n        from accounting.models import Expense, FixedAsset"

if old_import in r:
    r = r.replace(old_import, new_import)
    rp.write_text(r, encoding="utf-8")
    print("   fixed CashFlow import error")
else:
    print("   [WARN] Could not find exact import statement.")

# ─── 2. FRONTEND: Install Export Packages ──────────────────────────────
print("\n==> Installing export packages (jspdf, jspdf-autotable, xlsx)")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    sh(npm, "install", "jspdf", "jspdf-autotable", "xlsx", cwd=FRONTEND)

# ─── 3. FRONTEND: Create Export Utility ────────────────────────────────
print("\n==> Creating src/utils/export.ts")
write_frontend("src/utils/export.ts", '''\
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import * as XLSX from "xlsx";

export function exportToPDF(title: string, columns: string[], rows: any[][]) {
  const doc = new jsPDF();
  doc.text(title, 14, 15);
  autoTable(doc, {
    head: [columns],
    body: rows,
    startY: 20,
    theme: "grid",
    styles: { fontSize: 10, cellPadding: 3 },
    headStyles: { fillColor: [2, 132, 199] }, // Sky 600
  });
  doc.save(`${title.replace(/\\s+/g, "_")}.pdf`);
}

export function exportToExcel(title: string, columns: string[], rows: any[][]) {
  const wsData = [columns, ...rows];
  const ws = XLSX.utils.aoa_to_sheet(wsData);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Report");
  XLSX.writeFile(wb, `${title.replace(/\\s+/g, "_")}.xlsx`);
}
''')

# ─── 4. FRONTEND: Update FinancialReports.tsx ──────────────────────────
print("==> Updating src/pages/FinancialReports.tsx")
CONTENT = '''\
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { exportToPDF, exportToExcel } from "../utils/export";
import { FileSpreadsheet, FileText } from "lucide-react";

export default function FinancialReports() {
  const [tab, setTab] = useState<"pl" | "bs" | "cf" | "ar" | "tb">("pl");

  const pl = useQuery({ queryKey: ["report-pl"], queryFn: async () => (await api.get("/reports/profit-loss/")).data });
  const bs = useQuery({ queryKey: ["report-bs"], queryFn: async () => (await api.get("/reports/balance-sheet/")).data });
  const tb = useQuery({ queryKey: ["report-tb"], queryFn: async () => (await api.get("/reports/trial-balance/")).data });
  const cf = useQuery({ queryKey: ["report-cf"], queryFn: async () => (await api.get("/reports/cash-flow/")).data });
  const ar = useQuery({ queryKey: ["report-ar"], queryFn: async () => (await api.get("/reports/ar-aging/")).data });

  // --- Export Handlers ---
  const handleExportPL = (type: "pdf" | "excel") => {
    if (!pl.data) return;
    const rows = [
      ["Revenue", ""],
      ...pl.data.revenues.map((r: any) => [r.name, r.amount]),
      ["Total Revenue", pl.data.total_revenue],
      ["", ""],
      ["Expenses", ""],
      ...pl.data.expenses.map((e: any) => [e.name, e.amount]),
      ["Total Expenses", pl.data.total_expense],
      ["", ""],
      ["Net Profit / (Loss)", pl.data.net_profit]
    ];
    if (type === "pdf") exportToPDF("Profit & Loss", ["Account", "Amount (ZMW)"], rows);
    else exportToExcel("Profit & Loss", ["Account", "Amount (ZMW)"], rows);
  };

  const handleExportBS = (type: "pdf" | "excel") => {
    if (!bs.data) return;
    const rows = [
      ["Assets", ""],
      ...bs.data.assets.map((a: any) => [a.name, a.balance]),
      ["Total Assets", bs.data.total_assets],
      ["", ""],
      ["Liabilities & Equity", ""],
      ...bs.data.liabilities.map((l: any) => [l.name, l.balance]),
      ...bs.data.equity.map((e: any) => [e.name, e.balance]),
      ["Total Liabilities & Equity", bs.data.liabilities_and_equity]
    ];
    if (type === "pdf") exportToPDF("Balance Sheet", ["Account", "Balance (ZMW)"], rows);
    else exportToExcel("Balance Sheet", ["Account", "Balance (ZMW)"], rows);
  };

  const handleExportCF = (type: "pdf" | "excel") => {
    if (!cf.data) return;
    const rows = [
      ["Operating Activities", ""],
      ["Cash received from patients", cf.data.operating.payments_in],
      ["Cash paid for expenses", cf.data.operating.expenses_out],
      ["Net Cash from Operations", cf.data.operating.net],
      ["", ""],
      ["Investing Activities", ""],
      ["Purchase of Fixed Assets", cf.data.investing.fixed_assets],
      ["Net Cash from Investing", cf.data.investing.net],
      ["", ""],
      ["Net Increase / (Decrease) in Cash", cf.data.net_cash_flow]
    ];
    if (type === "pdf") exportToPDF("Cash Flow Statement", ["Item", "Amount (ZMW)"], rows);
    else exportToExcel("Cash Flow Statement", ["Item", "Amount (ZMW)"], rows);
  };

  const handleExportAR = (type: "pdf" | "excel") => {
    if (!ar.data) return;
    const rows = [
      ["Current (0-30 days)", ar.data.buckets["0_30"]],
      ["31-60 Days", ar.data.buckets["31_60"]],
      ["61-90 Days", ar.data.buckets["61_90"]],
      ["90+ Days (High Risk)", ar.data.buckets["90_plus"]],
      ["", ""],
      ["Total Outstanding", ar.data.total_outstanding]
    ];
    if (type === "pdf") exportToPDF("AR Aging", ["Bucket", "Amount (ZMW)"], rows);
    else exportToExcel("AR Aging", ["Bucket", "Amount (ZMW)"], rows);
  };

  const handleExportTB = (type: "pdf" | "excel") => {
    if (!tb.data) return;
    const rows = tb.data.accounts.map((a: any) => [a.code, a.name, a.debit, a.credit]);
    rows.push(["", "Totals", tb.data.total_debit, tb.data.total_credit]);
    if (type === "pdf") exportToPDF("Trial Balance", ["Code", "Account", "Debit", "Credit"], rows);
    else exportToExcel("Trial Balance", ["Code", "Account", "Debit", "Credit"], rows);
  };

  // Helper to render export buttons based on active tab
  const renderExportButtons = () => {
    let handler: ((t: "pdf" | "excel") => void) | null = null;
    if (tab === "pl") handler = handleExportPL;
    if (tab === "bs") handler = handleExportBS;
    if (tab === "cf") handler = handleExportCF;
    if (tab === "ar") handler = handleExportAR;
    if (tab === "tb") handler = handleExportTB;
    
    if (!handler) return null;

    return (
      <div className="flex gap-2">
        <button onClick={() => handler("excel")} className="flex items-center gap-2 text-sm font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-3 py-1.5 rounded-lg border border-emerald-200 transition">
          <FileSpreadsheet size={16} /> Excel
        </button>
        <button onClick={() => handler("pdf")} className="flex items-center gap-2 text-sm font-medium text-red-700 bg-red-50 hover:bg-red-100 px-3 py-1.5 rounded-lg border border-red-200 transition">
          <FileText size={16} /> PDF
        </button>
      </div>
    );
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Financial Reports</h1>
          <p className="text-sm text-slate-500 mt-1">IFRS-aligned financial statements.</p>
        </div>
        {renderExportButtons()}
      </div>

      <div className="flex gap-4 border-b overflow-x-auto">
        <button onClick={() => setTab("pl")} className={`pb-2 px-1 font-medium whitespace-nowrap ${tab === "pl" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Profit & Loss</button>
        <button onClick={() => setTab("bs")} className={`pb-2 px-1 font-medium whitespace-nowrap ${tab === "bs" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Balance Sheet</button>
        <button onClick={() => setTab("cf")} className={`pb-2 px-1 font-medium whitespace-nowrap ${tab === "cf" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Cash Flow</button>
        <button onClick={() => setTab("ar")} className={`pb-2 px-1 font-medium whitespace-nowrap ${tab === "ar" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>AR Aging</button>
        <button onClick={() => setTab("tb")} className={`pb-2 px-1 font-medium whitespace-nowrap ${tab === "tb" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Trial Balance</button>
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

      {tab === "cf" && cf.data && (
        <div className="bg-white border rounded-xl p-8 shadow-sm max-w-2xl mx-auto">
          <h2 className="text-xl font-bold text-center mb-6">Cash Flow Statement</h2>
          <p className="text-center text-sm text-slate-500 mb-6">{cf.data.period}</p>
          
          <h3 className="font-semibold text-slate-700 border-b pb-2 mb-2">Operating Activities</h3>
          <ul className="space-y-2 mb-6 text-sm">
            <li className="flex justify-between"><span>Cash received from patients</span><span>ZMW {cf.data.operating.payments_in}</span></li>
            <li className="flex justify-between"><span>Cash paid for expenses</span><span>ZMW {cf.data.operating.expenses_out}</span></li>
            <li className="flex justify-between font-bold border-t pt-2"><span>Net Cash from Operations</span><span>ZMW {cf.data.operating.net}</span></li>
          </ul>

          <h3 className="font-semibold text-slate-700 border-b pb-2 mb-2">Investing Activities</h3>
          <ul className="space-y-2 mb-6 text-sm">
            <li className="flex justify-between"><span>Purchase of Fixed Assets</span><span>ZMW {cf.data.investing.fixed_assets}</span></li>
            <li className="flex justify-between font-bold border-t pt-2"><span>Net Cash from Investing</span><span>ZMW {cf.data.investing.net}</span></li>
          </ul>

          <div className={`flex justify-between font-bold text-lg p-4 rounded-lg ${cf.data.net_cash_flow >= 0 ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>
            <span>Net Increase / (Decrease) in Cash</span>
            <span>ZMW {cf.data.net_cash_flow}</span>
          </div>
        </div>
      )}

      {tab === "ar" && ar.data && (
        <div className="bg-white border rounded-xl p-8 shadow-sm max-w-2xl mx-auto">
          <h2 className="text-xl font-bold text-center mb-2">Accounts Receivable Aging</h2>
          <p className="text-center text-sm text-slate-500 mb-6">Outstanding balances by age</p>
          <div className="flex justify-between font-bold text-lg border-b pb-4 mb-4">
            <span>Total Outstanding</span>
            <span className="text-red-600">ZMW {ar.data.total_outstanding}</span>
          </div>
          <ul className="space-y-3 text-sm">
            <li className="flex justify-between bg-slate-50 p-3 rounded"><span>Current (0-30 days)</span><span className="font-medium">ZMW {ar.data.buckets["0_30"]}</span></li>
            <li className="flex justify-between bg-amber-50 p-3 rounded"><span>31-60 Days</span><span className="font-medium text-amber-700">ZMW {ar.data.buckets["31_60"]}</span></li>
            <li className="flex justify-between bg-orange-50 p-3 rounded"><span>61-90 Days</span><span className="font-medium text-orange-700">ZMW {ar.data.buckets["61_90"]}</span></li>
            <li className="flex justify-between bg-red-50 p-3 rounded"><span>90+ Days (High Risk)</span><span className="font-medium text-red-700">ZMW {ar.data.buckets["90_plus"]}</span></li>
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
'''
write_frontend("src/pages/FinancialReports.tsx", CONTENT)

# ─── 5. Build & Push ───────────────────────────────────────────────────
print("\n==> Running local Vite build to verify")
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
def sh_git(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)

sh_git("git", "add", ".")
sh_git("git", "commit", "-m", "fix(cashflow): fix backend import and add PDF/Excel export to all reports")
sh_git("git", "push", "origin", "main")

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")