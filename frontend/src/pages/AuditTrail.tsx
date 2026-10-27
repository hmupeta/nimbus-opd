import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function AuditTrail() {
  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: async () => (await api.get<Paginated<any>>("/audit-logs/")).data.results,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Audit Trail</h1>
        <p className="text-sm text-slate-500 mt-1">A complete log of every data change in the clinic (most recent 200 events).</p>
      </div>

      {isLoading && <p className="text-slate-500">Loading…</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Time</th>
              <th className="text-left px-4 py-3">User</th>
              <th className="text-left px-4 py-3">Action</th>
              <th className="text-left px-4 py-3">Record</th>
              <th className="text-left px-4 py-3">Changes</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.map((log: any) => (
              <tr key={log.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                  {new Date(log.at).toLocaleString()}
                </td>
                <td className="px-4 py-3 font-medium">{log.user_email}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                    log.action === "create" ? "bg-emerald-100 text-emerald-700" :
                    log.action === "delete" ? "bg-red-100 text-red-700" :
                    "bg-sky-100 text-sky-700"
                  }`}>
                    {log.action.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-mono text-xs bg-slate-100 px-2 py-0.5 rounded">
                    {log.model_name} #{log.object_id}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-500 max-w-xs truncate">
                  {log.action === "update" ? (
                    <span>
                      {Object.keys(log.after || {}).filter(k => log.before?.[k] !== log.after?.[k]).join(", ")}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
            {data?.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-slate-500">No audit logs found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
