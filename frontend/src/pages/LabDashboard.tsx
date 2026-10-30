import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated, LabOrder } from "../api/types";

export default function LabDashboard() {
  const qc = useQueryClient();
  const [activeOrder, setActiveOrder] = useState<LabOrder | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["lab-orders", "pending"],
    queryFn: async () =>
      (await api.get<Paginated<LabOrder>>("/lab-orders/?status=pending")).data,
  });

  const submitResult = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: FormData }) => {
      await api.post(`/lab-orders/${id}/result/`, payload, {
        headers: { "Content-Type": "multipart/form-data" }
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lab-orders"] });
      setActiveOrder(null);
    },
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!activeOrder) return;
    const fd = new FormData(e.currentTarget);
    submitResult.mutate({
      id: activeOrder.id,
      payload: {
        value_text: String(fd.get("value_text") || ""),
        unit: String(fd.get("unit") || ""),
        flag: String(fd.get("flag") || "normal"),
        comment: String(fd.get("comment") || ""),
      },
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Laboratory Queue</h1>

      {isLoading && <p className="text-slate-500">Loading…</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Order Time</th>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Test</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.results.map((o) => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-500">
                  {new Date(o.ordered_at).toLocaleTimeString()}
                </td>
                <td className="px-4 py-3 font-medium">{o.patient_name}</td>
                <td className="px-4 py-3">
                  {o.test_name} <span className="text-xs text-slate-400 font-mono">({o.test_code})</span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">
                    {o.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {o.status === "pending" ? (
                    <button
                      onClick={() => setActiveOrder(o)}
                      className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700"
                    >
                      Record Result
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400 font-medium">Completed</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.results.length === 0 && (
          <p className="p-6 text-center text-slate-500">No pending lab tests.</p>
        )}
      </div>

      {activeOrder && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-4 border-b flex justify-between items-center">
              <h2 className="font-semibold text-lg">Record Result</h2>
              <button onClick={() => setActiveOrder(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={onSubmit} className="p-4 space-y-4">
              <div className="bg-slate-50 p-3 rounded text-sm mb-4">
                <p><span className="text-slate-500">Patient:</span> <b>{activeOrder.patient_name}</b></p>
                <p><span className="text-slate-500">Test:</span> <b>{activeOrder.test_name}</b></p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <label className="block text-sm">
                  <span className="text-slate-600">Result Value *</span>
                  <input name="value_text" required className="mt-1 w-full border rounded px-3 py-2" />
                </label>
                <label className="block text-sm">
                  <span className="text-slate-600">Unit</span>
                  <input name="unit" defaultValue={activeOrder.test_code === "CBC" ? "10^9/L" : ""} className="mt-1 w-full border rounded px-3 py-2" />
                </label>
              </div>
              <label className="block text-sm">
                <span className="text-slate-600">Flag</span>
                <select name="flag" className="mt-1 w-full border rounded px-3 py-2">
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="low">Low</option>
                  <option value="critical">Critical</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Comments</span>
                <textarea name="comment" rows={2} className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Attach Result Slip (PDF / Image)</span>
                <input type="file" name="attachment" accept="image/*,application/pdf" className="mt-1 w-full border rounded px-3 py-2 bg-white" />
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setActiveOrder(null)} className="px-4 py-2 text-sm text-slate-600 border rounded hover:bg-slate-50">Cancel</button>
                <button type="submit" disabled={submitResult.isPending} className="px-4 py-2 text-sm text-white bg-emerald-600 rounded hover:bg-emerald-700">
                  {submitResult.isPending ? "Saving..." : "Save Result"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
