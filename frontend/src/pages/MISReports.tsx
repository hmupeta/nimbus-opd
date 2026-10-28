import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";

const COLORS = ["#0284c7", "#10b981", "#6366f1", "#f59e0b"];

export default function MISReports() {
  const { data, isLoading } = useQuery({
    queryKey: ["mis-reports"],
    queryFn: async () => (await api.get("/reports/mis/")).data,
  });

  if (isLoading) return <p className="text-slate-500">Loading reports…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-800">Management Reports</h1>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white border rounded-lg p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4 text-slate-700">
            Doctor Throughput
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.doctor_throughput || []}>
                <XAxis
                  dataKey="doctor"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12 }}
                />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar
                  dataKey="patients"
                  fill="#0284c7"
                  radius={[4, 4, 0, 0]}
                  name="Patients Seen"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border rounded-lg p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4 text-slate-700">
            Revenue by Payer Mix
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data?.payer_mix || []}
                  dataKey="amount"
                  nameKey="method"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label
                >
                  {data?.payer_mix?.map((entry: any, index: number) => (
                    <Cell
                      key={entry.name || `cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip formatter={(value: any) => `ZMW ${value}`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-white border rounded-lg p-6 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-700">
            Lab Turnaround Time (TAT)
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Average time from order to result completion.
          </p>
        </div>
        <div className="text-center">
          <p className="text-4xl font-bold text-indigo-600">
            {data?.lab_tat_minutes}{" "}
            <span className="text-xl text-slate-500">mins</span>
          </p>
          <p className="text-xs text-slate-400 mt-1">
            {data?.lab_volume} tests processed
          </p>
        </div>
      </div>
    </div>
  );
}
