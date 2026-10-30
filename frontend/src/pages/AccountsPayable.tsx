import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function AccountsPayable() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const data = useQuery({
    queryKey: ["bills"],
    queryFn: async () => (await api.get<Paginated<any>>("/bills/")).data.results,
  });

  const options = useQuery({
    queryKey: ["finance-options-bills"],
    queryFn: async () => {
        const suppliers = await api.get<Paginated<any>>("/suppliers/").then(r => r.data.results);
        return { suppliers };
    }
  });

  const createItem = useMutation({
    mutationFn: async (payload: any) => await api.post("/bills/", payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["bills"] }); setShowForm(false); },
  });

  function onSubmit(e: any) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: any = {};
    fd.forEach((v, k) => payload[k] = v);
    createItem.mutate(payload);
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-800">Accounts Payable</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium">
          + New Accounts Payable
        </button>
      </div>

      {showForm && (
        <form onSubmit={onSubmit} className="bg-white border rounded-xl p-6 shadow-sm grid grid-cols-2 gap-4">
            <label className="block text-sm"><span className="text-slate-600">Reference</span>
              <input type="text" name="reference" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm"><span className="text-slate-600">Date</span>
              <input type="date" name="date" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm"><span className="text-slate-600">Amount (ZMW)</span>
              <input type="number" name="amount" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm"><span className="text-slate-600">Supplier</span>
              <select name="supplier" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="">Select...</option>
                {options.suppliers?.map((o: any) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </label>
          <div className="col-span-2 flex justify-end gap-2 pt-4">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 border rounded-lg text-slate-600">Cancel</button>
            <button type="submit" disabled={createItem.isPending} className="px-4 py-2 bg-sky-600 text-white rounded-lg">Save</button>
          </div>
        </form>
      )}

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr><th className="text-left px-4 py-3">Supplier</th><th className="text-left px-4 py-3">Date</th><th className="text-left px-4 py-3">Amount</th><th className="text-left px-4 py-3">Status</th></tr></thead>
          <tbody className="divide-y">
            {data.data?.map((row: any) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">{row.supplier_name}</td><td className="px-4 py-3">{row.date}</td><td className="px-4 py-3">{row.amount}</td><td className="px-4 py-3">{row.status}</td>
              </tr>
            ))}
            {data.data?.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">No records yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}