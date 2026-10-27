import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function RadiologyDashboard() {
  const qc = useQueryClient();
  const [activeOrder, setActiveOrder] = useState<any | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["rad-orders", "pending"],
    queryFn: async () => (await api.get<Paginated<any>>("/radiology-orders/?status=pending")).data,
  });

  const submitReport = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: any }) => {
      await api.post(`/radiology-orders/${id}/report/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rad-orders"] });
      setActiveOrder(null);
    },
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!activeOrder) return;
    const fd = new FormData(e.currentTarget);
    submitReport.mutate({
      id: activeOrder.id,
      payload: fd, // Pass FormData directly
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Radiology Queue</h1>
      {isLoading && <p className="text-slate-500">Loading…</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Examination</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.results.map((o: any) => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{o.patient_name}</p>
                  <p className="text-xs text-slate-400">{o.visit_no}</p>
                </td>
                <td className="px-4 py-3">
                  <span className="font-medium">{o.modality}</span> - {o.body_part}
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">{o.status}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  {o.status === "pending" ? (
                    <button onClick={() => setActiveOrder(o)} className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700">
                      Enter Report
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400 font-medium">Reported</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.results.length === 0 && <p className="p-6 text-center text-slate-500">No pending radiology orders.</p>}
      </div>

      {activeOrder && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg">
            <div className="p-4 border-b flex justify-between items-center">
              <h2 className="font-semibold text-lg">Radiology Report</h2>
              <button onClick={() => setActiveOrder(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={onSubmit} className="p-4 space-y-4">
              <div className="bg-slate-50 p-3 rounded text-sm mb-4">
                <p><span className="text-slate-500">Patient:</span> <b>{activeOrder.patient_name}</b></p>
                <p><span className="text-slate-500">Exam:</span> <b>{activeOrder.modality} {activeOrder.body_part}</b></p>
              </div>
              <label className="block text-sm">
                <span className="text-slate-600">Findings</span>
                <textarea name="findings" rows={4} required className="mt-1 w-full border rounded px-3 py-2" placeholder="Describe the radiographic findings..." />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Impression / Conclusion</span>
                <textarea name="impression" rows={2} required className="mt-1 w-full border rounded px-3 py-2" placeholder="Normal, abnormal, etc." />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Attach Digital Image (JPG/PNG)</span>
                <input type="file" name="image" accept="image/*" className="mt-1 w-full border rounded px-3 py-2 bg-white" />
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setActiveOrder(null)} className="px-4 py-2 text-sm text-slate-600 border rounded hover:bg-slate-50">Cancel</button>
                <button type="submit" disabled={submitReport.isPending} className="px-4 py-2 text-sm text-white bg-emerald-600 rounded hover:bg-emerald-700">
                  {submitReport.isPending ? "Saving..." : "Save Report"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
