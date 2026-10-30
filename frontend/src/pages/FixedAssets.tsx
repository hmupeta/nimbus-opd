import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function FixedAsset() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const data = useQuery({
    queryKey: ["fixed-assets"],
    queryFn: async () => (await api.get<Paginated<any>>("/fixed-assets/")).data.results,
  });

  const options = useQuery({
    queryKey: ["finance-options-fixed-assets"],
    queryFn: async () => {
        const coa = await api.get<Paginated<any>>("/chart-of-accounts/").then(r => r.data.results);
        return { coa };
    }
  });

  const createItem = useMutation({
    mutationFn: async (payload: any) => await api.post("/fixed-assets/", payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["fixed-assets"] }); setShowForm(false); },
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
        <h1 className="text-2xl font-semibold text-slate-800">Fixed Asset</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium">
          + New Fixed Asset
        </button>
      </div>

      {showForm && (
        <form onSubmit={onSubmit} className="bg-white border rounded-xl p-6 shadow-sm grid grid-cols-2 gap-4">
            <label className="block text-sm"><span className="text-slate-600">Name</span>
              <input type="text" name="name" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm"><span className="text-slate-600">Purchase Date</span>
              <input type="date" name="purchase_date" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm"><span className="text-slate-600">Cost (ZMW)</span>
              <input type="number" name="purchase_cost" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm"><span className="text-slate-600">Category</span>
              <select name="category" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="">Select...</option>
                {options.coa?.map((o: any) => <option key={o.id} value={o.id}>{o.name}</option>)}
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
          <thead className="bg-slate-50 text-slate-600"><tr><th className="text-left px-4 py-3">Name</th><th className="text-left px-4 py-3">Purchase Date</th><th className="text-left px-4 py-3">Cost</th><th className="text-left px-4 py-3">Category</th></tr></thead>
          <tbody className="divide-y">
            {data.data?.map((row: any) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">{row.name}</td><td className="px-4 py-3">{row.purchase_date}</td><td className="px-4 py-3">{row.purchase_cost}</td><td className="px-4 py-3">{row.category_name}</td>
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