import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PharmacistDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-orders", "dashboard"],
    queryFn: async () => (await api.get<Paginated<any>>("/pharmacy-orders/")).data.results,
  });

  if (isLoading) return <p className="text-slate-500">Loading summary…</p>;

  const pending = data?.filter((o: any) => o.status === "pending") || [];
  const dispensed = data?.filter((o: any) => o.status === "dispensed") || [];
  
  // Calculate total drugs handed out
  const totalItemsDispensed = dispensed.reduce((acc: number, o: any) => {
    return acc + o.items.reduce((sum: number, i: any) => sum + i.quantity_dispensed, 0);
  }, 0);

  // Unique patients served (by visit ID)
  const uniquePatients = new Set(dispensed.map((o: any) => o.visit_no)).size;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Pharmacy Overview</h1>
        <Link to="/pharmacy" className="bg-sky-600 text-white px-4 py-2 rounded text-sm hover:bg-sky-700">
          Go to Dispensing Queue →
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Pending Prescriptions" value={pending.length} color="amber" />
        <StatCard title="Patients Served" value={uniquePatients} color="emerald" />
        <StatCard title="Total Drugs Dispensed" value={totalItemsDispensed} color="sky" />
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-700 mb-2">Recent Dispensations</h2>
        <p className="text-sm text-slate-500 mb-4">The last 5 completed orders.</p>
        <ul className="divide-y text-sm">
          {dispensed.slice(0, 5).map((o: any) => (
            <li key={o.id} className="py-3 flex justify-between items-center">
              <div>
                <p className="font-medium text-slate-800">{o.patient_name || o.visit_no}</p>
                <p className="text-xs text-slate-500">
                  {o.items.map((i: any) => `${i.quantity_dispensed}x ${i.medicine_name}`).join(", ")}
                </p>
              </div>
              <span className="text-xs text-slate-400">
                {new Date(o.dispensed_at).toLocaleTimeString()}
              </span>
            </li>
          ))}
          {dispensed.length === 0 && <li className="py-4 text-slate-500 text-center">No dispensations yet.</li>}
        </ul>
      </div>
    </div>
  );
}

function StatCard({ title, value, color }: { title: string, value: number, color: string }) {
  const colors: any = {
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
    sky: "bg-sky-50 border-sky-200 text-sky-700",
  };
  return (
    <div className={`border rounded-lg p-5 ${colors[color]}`}>
      <p className="text-sm font-medium opacity-80">{title}</p>
      <p className="text-3xl font-bold mt-2">{value}</p>
    </div>
  );
}
