import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api/client";
import { currentUser } from "../api/auth";
import type { DashboardSummary, Paginated, Visit } from "../api/types";
import PharmacistDashboard from "./PharmacistDashboard";
import LabTechDashboard from "./LabTechDashboard";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ['#0284c7', '#10b981', '#6366f1', '#f59e0b', '#ef4444'];

export default function Dashboard() {
  const user = currentUser();
  
  if (user?.is_platform_admin) return <Navigate to="/platform" replace />;
  if (user?.role === "lab") return <LabTechDashboard />;
  if (user?.role === "pharmacist") return <PharmacistDashboard />;
  if (user?.role === "receptionist") return <Navigate to="/billing" replace />;
  if (user?.role === "radiology") return <Navigate to="/radiology" replace />;

  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get<DashboardSummary>("/reports/dashboard/")).data,
  });

  const visits = useQuery({
    queryKey: ["visits", "active"],
    queryFn: async () => {
      const activeStatuses = ["open", "triaged", "in_consultation"];
      const results = await Promise.all(
        activeStatuses.map((s) =>
          api.get<Paginated<Visit>>(`/visits/?status=${s}`).then((r) => r.data.results)
        )
      );
      return results.flat();
    },
  });

  const analytics = useQuery({
    queryKey: ["analytics", "trend"],
    queryFn: async () => (await api.get("/analytics/trend/")).data,
  });

  const nursingQueue = visits.data?.filter((v) => v.status === "open") || [];
  const doctorQueue = visits.data?.filter((v) => v.status === "triaged" || v.status === "in_consultation") || [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Clinic Dashboard</h1>

      {summary.data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Today's visits" value={summary.data.census.total} />
          <Stat label="Waiting for Nurse" value={nursingQueue.length} />
          <Stat label="Waiting for Doctor" value={doctorQueue.length} />
          <Stat label="Revenue today" value={`ZMW ${summary.data.revenue.today}`} />
        </div>
      )}

      {/* Charts Row */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-white border rounded-lg p-4 md:col-span-2 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Patient Footfall & Revenue (Last 7 Days)</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.data?.trend || []}>
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <YAxis yAxisId="left" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar yAxisId="left" dataKey="visits" fill="#0284c7" radius={[4,4,0,0]} name="Patients" />
                <Bar yAxisId="right" dataKey="revenue" fill="#10b981" radius={[4,4,0,0]} name="Revenue (ZMW)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border rounded-lg p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Revenue Breakdown</h2>
          <div className="h-64 flex items-center justify-center">
            {(analytics.data?.category_breakdown?.length || 0) > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={analytics.data.category_breakdown} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {analytics.data.category_breakdown.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-500 text-sm">No revenue data yet.</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Nursing Queue */}
        <section>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-lg font-semibold text-sky-800">Nursing Queue</h2>
            <span className="bg-sky-100 text-sky-700 text-xs px-2 py-0.5 rounded-full">{nursingQueue.length}</span>
          </div>
          <ul className="divide-y border rounded-lg bg-white">
            {nursingQueue.map((v) => (
              <li key={v.id}>
                <Link to={`/visits/${v.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50">
                  <div>
                    <p className="font-medium">{v.patient_name}</p>
                    <p className="text-sm text-slate-500">{v.visit_no}</p>
                  </div>
                  <span className="text-xs bg-sky-100 text-sky-700 rounded px-2 py-0.5 font-medium">Record Vitals →</span>
                </Link>
              </li>
            ))}
            {nursingQueue.length === 0 && <li className="p-4 text-slate-500 text-sm text-center">No patients waiting.</li>}
          </ul>
        </section>

        {/* Doctor's Queue */}
        <section>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-lg font-semibold text-emerald-800">Doctor's Queue</h2>
            <span className="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded-full">{doctorQueue.length}</span>
          </div>
          <ul className="divide-y border rounded-lg bg-white">
            {doctorQueue.map((v) => (
              <li key={v.id}>
                <Link to={`/visits/${v.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50">
                  <div>
                    <p className="font-medium">{v.patient_name}</p>
                    <p className="text-sm text-slate-500">{v.visit_no}</p>
                  </div>
                  <span className={`text-xs rounded px-2 py-0.5 font-medium ${v.status === 'triaged' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                    {v.status === 'triaged' ? 'Start Consult →' : 'In Consult'}
                  </span>
                </Link>
              </li>
            ))}
            {doctorQueue.length === 0 && <li className="p-4 text-slate-500 text-sm text-center">No patients waiting.</li>}
          </ul>
        </section>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}
