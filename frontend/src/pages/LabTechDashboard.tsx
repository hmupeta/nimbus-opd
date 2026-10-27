import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function LabTechDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["lab-orders", "dashboard"],
    queryFn: async () => (await api.get<Paginated<any>>("/lab-orders/")).data.results,
  });

  if (isLoading) return <p className="text-slate-500">Loading summary…</p>;

  const pending = data?.filter((o: any) => o.status === "pending") || [];
  const completed = data?.filter((o: any) => o.status === "completed") || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Laboratory Overview</h1>
        <Link to="/lab" className="bg-sky-600 text-white px-4 py-2 rounded text-sm hover:bg-sky-700">
          Go to Lab Queue →
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatCard title="Pending Tests" value={pending.length} color="amber" />
        <StatCard title="Completed Tests" value={completed.length} color="emerald" />
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-700 mb-2">Recent Completed Tests</h2>
        <p className="text-sm text-slate-500 mb-4">The last 5 results recorded by the lab.</p>
        <ul className="divide-y text-sm">
          {completed.slice(0, 5).map((o: any) => (
            <li key={o.id} className="py-3 flex justify-between items-center">
              <div>
                <p className="font-medium text-slate-800">{o.patient_name || o.visit_no}</p>
                <p className="text-xs text-slate-500">
                  {o.test_name} {o.result ? `(Result: ${o.result.value_text} ${o.result.unit})` : ""}
                </p>
              </div>
              <span className="text-xs text-slate-400">
                {new Date(o.completed_at).toLocaleTimeString()}
              </span>
            </li>
          ))}
          {completed.length === 0 && <li className="py-4 text-slate-500 text-center">No completed tests yet.</li>}
        </ul>
      </div>
    </div>
  );
}

function StatCard({ title, value, color }: { title: string, value: number, color: string }) {
  const colors: any = {
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
  };
  return (
    <div className={`border rounded-lg p-5 ${colors[color]}`}>
      <p className="text-sm font-medium opacity-80">{title}</p>
      <p className="text-3xl font-bold mt-2">{value}</p>
    </div>
  );
}
