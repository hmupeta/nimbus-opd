import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PharmacyDashboard() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-orders"],
    queryFn: async () => {
      // Fetch both pending and dispensed so we have a full history
      const pending = await api.get<Paginated<any>>("/pharmacy-orders/?status=pending");
      const dispensed = await api.get<Paginated<any>>("/pharmacy-orders/?status=dispensed");
      return [...pending.data.results, ...dispensed.data.results];
    },
  });

  const dispense = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/pharmacy-orders/${id}/dispense/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pharmacy-orders"] }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Pharmacy Queue</h1>
      {isLoading && <p className="text-slate-500">Loading…</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Medications (Prescribed → Dispensed)</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.map((o: any) => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{o.patient_name || o.visit_no}</p>
                  <p className="text-xs text-slate-400">{o.visit_no}</p>
                </td>
                <td className="px-4 py-3">
                  <ul className="text-xs space-y-1">
                    {o.items.map((i: any) => (
                      <li key={i.id} className="flex items-center gap-2">
                        <span className="font-medium text-slate-700">{i.medicine_name}</span>
                        <span className="text-slate-500">({i.dose} {i.frequency})</span>
                        <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                          Qty: {i.quantity_prescribed} → <b className={i.quantity_dispensed > 0 ? "text-emerald-600" : "text-slate-400"}>{i.quantity_dispensed}</b>
                        </span>
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded ${o.status === 'dispensed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {o.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {o.status === "pending" ? (
                    <button
                      onClick={() => dispense.mutate(o.id)}
                      disabled={dispense.isPending}
                      className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700 disabled:opacity-50"
                    >
                      Dispense
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400">Completed</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.length === 0 && <p className="p-6 text-center text-slate-500">No prescriptions found.</p>}
      </div>
    </div>
  );
}
