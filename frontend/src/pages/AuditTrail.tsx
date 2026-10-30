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
      
      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3 w-32">Time</th>
              <th className="text-left px-4 py-3 w-48">User</th>
              <th className="text-left px-4 py-3 w-24">Action</th>
              <th className="text-left px-4 py-3 w-64">Record</th>
              <th className="text-left px-4 py-3">Changes</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.map((log: any) => (
              <tr key={log.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-500 whitespace-nowrap text-xs">
                  {new Date(log.at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'medium' })}
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-800">{log.user_name}</div>
                  <div className="text-xs text-slate-400">{log.user_email}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wide ${
                    log.action === "create" ? "bg-emerald-100 text-emerald-700" :
                    log.action === "delete" ? "bg-red-100 text-red-700" :
                    "bg-sky-100 text-sky-700"
                  }`}>
                    {log.action}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-medium text-slate-700 block truncate max-w-[240px]" title={log.record_name}>
                    {log.record_name}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs">
                  {log.changes && log.changes.length > 0 ? (
                    <ul className="space-y-1">
                      {log.changes.map((c: any, idx: number) => (
                        <li key={idx} className="bg-slate-50 p-1.5 rounded border border-slate-100">
                          <span className="font-semibold text-slate-600">{c.field}:</span>{" "}
                          <span className="text-red-500 line-through opacity-70">{String(c.old || "empty")}</span>{" "}
                          <span className="text-slate-400">→</span>{" "}
                          <span className="text-emerald-600 font-medium">{String(c.new || "empty")}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-slate-400 italic">No field changes</span>
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