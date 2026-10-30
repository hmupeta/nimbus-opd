import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function ChartofAccounts() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const data = useQuery({
    queryKey: ["chart-of-accounts"],
    queryFn: async () => (await api.get<Paginated<any>>("/chart-of-accounts/")).data.results,
  });

  const options = useQuery({
    queryKey: ["finance-options-chart-of-accounts"],
    queryFn: async () => {
        return {};
    }
  });

  const createItem = useMutation({
    mutationFn: async (payload: any) => await api.post("/chart-of-accounts/", payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["chart-of-accounts"] }); setShowForm(false); },
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
        <h1 className="text-2xl font-semibold text-slate-800">Chart of Accounts</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium">
          + New Chart of Accounts
        </button>
      </div>

      {showForm && (
        <form onSubmit={onSubmit} className="bg-white border rounded-xl p-6 shadow-sm grid grid-cols-2 gap-4">
            <label className="block text-sm"><span className="text-slate-600">Code</span>
              <input type="text" name="code" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm"><span className="text-slate-600">Name</span>
              <input type="text" name="name" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm"><span className="text-slate-600">Type (asset/liability/equity/revenue/expense)</span>
              <input type="text" name="type" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
          <div className="col-span-2 flex justify-end gap-2 pt-4">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 border rounded-lg text-slate-600">Cancel</button>
            <button type="submit" disabled={createItem.isPending} className="px-4 py-2 bg-sky-600 text-white rounded-lg">Save</button>
          </div>
        </form>
      )}

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr><th className="text-left px-4 py-3">Code</th><th className="text-left px-4 py-3">Name</th><th className="text-left px-4 py-3">Type</th></tr></thead>
          <tbody className="divide-y">
            {data.data?.map((row: any) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">{row.code}</td><td className="px-4 py-3">{row.name}</td><td className="px-4 py-3">{row.type}</td>
              </tr>
            ))}
            {data.data?.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-500">No records yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}