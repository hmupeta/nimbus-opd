import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function Payments() {
  const payments = useQuery({
    queryKey: ["payments"],
    queryFn: async () => (await api.get<Paginated<any>>("/payments/")).data.results,
  });

  const getMethodColor = (method: string) => {
    switch (method) {
      case "cash": return "bg-emerald-100 text-emerald-700";
      case "mobile_money": return "bg-amber-100 text-amber-700";
      case "card": return "bg-indigo-100 text-indigo-700";
      case "insurance": return "bg-sky-100 text-sky-700";
      default: return "bg-slate-100 text-slate-700";
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Payments History</h1>
        <p className="text-sm text-slate-500 mt-1">A complete ledger of all payments received.</p>
      </div>

      {payments.isLoading && <p className="text-slate-500">Loading...</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3">Date & Time</th>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Visit No</th>
              <th className="text-left px-4 py-3">Amount</th>
              <th className="text-left px-4 py-3">Method</th>
              <th className="text-left px-4 py-3">Reference</th>
              <th className="text-left px-4 py-3">Received By</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {payments.data?.map((p: any) => (
              <tr key={p.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                  {new Date(p.paid_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}
                </td>
                <td className="px-4 py-3 font-medium text-slate-800">{p.patient_name}</td>
                <td className="px-4 py-3 font-mono text-xs">{p.visit_no}</td>
                <td className="px-4 py-3 font-bold text-slate-800">ZMW {p.amount}</td>
                <td className="px-4 py-3">
                  <span className={`text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wide ${getMethodColor(p.method)}`}>
                    {p.method.replace("_", " ")}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{p.reference || "—"}</td>
                <td className="px-4 py-3 text-slate-600">{p.received_by_name}</td>
              </tr>
            ))}
            {payments.data?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No payments recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}