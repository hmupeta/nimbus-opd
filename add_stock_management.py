#!/usr/bin/env python3
"""
add_stock_management.py
  - Adds a "Receive Stock" form to the StockDashboard.
  - Allows pharmacists to select a medicine, enter batch, expiry, and qty.
  - Updates the table to refresh instantly.
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

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, capture_output=True, text=True)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. Overwrite StockDashboard.tsx ───────────────────────────────────
print("==> Updating StockDashboard.tsx with Receive Stock form")
CONTENT = '''\
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function StockDashboard() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const stock = useQuery({
    queryKey: ["stock"],
    queryFn: async () => (await api.get<Paginated<any>>("/stock/")).data.results,
  });

  const medicines = useQuery({
    queryKey: ["medicines"],
    queryFn: async () => (await api.get<Paginated<any>>("/medicines/")).data.results,
  });

  const receiveStock = useMutation({
    mutationFn: async (payload: any) => {
      await api.post("/stock/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      setShowForm(false);
    },
  });

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    receiveStock.mutate({
      medicine: Number(fd.get("medicine")),
      batch_no: String(fd.get("batch_no")),
      expiry_date: String(fd.get("expiry_date")),
      quantity: Number(fd.get("quantity")),
    });
  }

  const isExpiring = (dateStr: string) => {
    const expiry = new Date(dateStr).getTime();
    const today = new Date().getTime();
    const days90 = 90 * 24 * 60 * 60 * 1000;
    return expiry - today < days90;
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Inventory & Stock Levels</h1>
          <p className="text-sm text-slate-500 mt-1">Monitor batches and expiry dates. <span className="text-red-500 font-medium">Red</span> indicates low stock or near expiry.</p>
        </div>
        <button 
          onClick={() => setShowForm(!showForm)} 
          className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium"
        >
          + Receive Stock
        </button>
      </div>

      {showForm && (
        <form onSubmit={onSubmit} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="font-bold text-lg">Receive New Stock</h2>
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm col-span-2">
              <span className="text-slate-600 font-medium">Medicine</span>
              <select name="medicine" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="">Select a medicine from catalog...</option>
                {medicines.data?.map((m: any) => (
                  <option key={m.id} value={m.id}>{m.name} {m.strength} ({m.code})</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-slate-600 font-medium">Batch Number</span>
              <input name="batch_no" required placeholder="e.g. BATCH-001" className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="text-sm">
              <span className="text-slate-600 font-medium">Expiry Date</span>
              <input type="date" name="expiry_date" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="text-sm col-span-2">
              <span className="text-slate-600 font-medium">Quantity Received</span>
              <input type="number" name="quantity" required min="1" placeholder="e.g. 500" className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 border rounded-lg text-slate-600">Cancel</button>
            <button type="submit" disabled={receiveStock.isPending} className="px-4 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-700">
              {receiveStock.isPending ? "Saving..." : "Save Stock"}
            </button>
          </div>
        </form>
      )}

      {stock.isLoading && <p className="text-slate-500">Loading...</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Medicine</th>
              <th className="text-left px-4 py-3">Batch No</th>
              <th className="text-left px-4 py-3">Expiry Date</th>
              <th className="text-left px-4 py-3">Qty Available</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {stock.data?.map((s: any) => {
              const lowStock = s.quantity < 50;
              const expiring = isExpiring(s.expiry_date);
              return (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{s.medicine_name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{s.batch_no}</td>
                  <td className={`px-4 py-3 ${expiring ? "text-red-600 font-bold" : ""}`}>{s.expiry_date}</td>
                  <td className={`px-4 py-3 font-bold ${lowStock ? "text-red-600" : "text-slate-700"}`}>{s.quantity}</td>
                </tr>
              );
            })}
            {stock.data?.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">No stock records found. Click "Receive Stock" to add inventory.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
'''
write_frontend("src/pages/StockDashboard.tsx", CONTENT)

# ─── 2. Build & Push ───────────────────────────────────────────────────
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
r = sh("git", "commit", "-m", "feat(pharmacy): add receive stock form to inventory dashboard", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")