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