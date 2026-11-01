import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { currentUser } from "../api/auth";
import type { Paginated } from "../api/types";

export default function AccountingDashboard() {
  const qc = useQueryClient();
  const user = currentUser();
  const isManager = user?.role === "finance_manager" || user?.role === "admin";
  const [expanded, setExpanded] = useState<number | null>(null);

  const entries = useQuery({
    queryKey: ["journal-entries"],
    queryFn: async () => (await api.get<Paginated<any>>("/journal-entries/")).data.results,
  });

  const approve = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/journal-entries/${id}/approve/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["journal-entries"] }),
  });

  const reject = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/journal-entries/${id}/reject/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["journal-entries"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">General Ledger</h1>
        <p className="text-sm text-slate-500 mt-1">Review and approve journal entries.</p>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3">Date</th>
              <th className="text-left px-4 py-3">Reference</th>
              <th className="text-left px-4 py-3">Description</th>
              <th className="text-left px-4 py-3">Status</th>
              {isManager && <th className="text-right px-4 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y">
            {entries.data?.map((je: any) => (
              <>
                <tr key={je.id} className="hover:bg-slate-50 cursor-pointer" onClick={() => setExpanded(expanded === je.id ? null : je.id)}>
                  <td className="px-4 py-3">{je.date}</td>
                  <td className="px-4 py-3 font-mono text-xs">{je.reference}</td>
                  <td className="px-4 py-3 text-slate-500">{je.description}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      je.status === "approved" ? "bg-emerald-100 text-emerald-700" :
                      je.status === "rejected" ? "bg-red-100 text-red-700" :
                      "bg-amber-100 text-amber-700"
                    }`}>
                      {je.status.toUpperCase()}
                    </span>
                  </td>
                  {isManager && (
                    <td className="px-4 py-3 text-right space-x-2" onClick={(e) => e.stopPropagation()}>
                      {je.status === "pending" && (
                        <>
                          <button onClick={() => approve.mutate(je.id)} className="text-xs bg-emerald-600 text-white px-3 py-1.5 rounded hover:bg-emerald-700">Approve</button>
                          <button onClick={() => reject.mutate(je.id)} className="text-xs bg-red-100 text-red-700 px-3 py-1.5 rounded hover:bg-red-200">Reject</button>
                        </>
                      )}
                    </td>
                  )}
                </tr>
                {expanded === je.id && (
                  <tr className="bg-slate-50 border-b">
                    <td colSpan={isManager ? 5 : 4} className="px-4 py-4">
                      <div className="pl-8">
                        <h4 className="font-semibold text-slate-700 mb-2">Journal Lines</h4>
                        <table className="w-full text-xs">
                          <thead className="text-slate-500 border-b">
                            <tr><th className="text-left py-1">Account</th><th className="text-right py-1">Debit</th><th className="text-right py-1">Credit</th></tr>
                          </thead>
                          <tbody>
                            {je.lines.map((line: any) => (
                              <tr key={line.id}>
                                <td className="py-1">{line.account_name}</td>
                                <td className="py-1 text-right text-slate-700">{line.debit > 0 ? `ZMW ${line.debit}` : "—"}</td>
                                <td className="py-1 text-right text-slate-700">{line.credit > 0 ? `ZMW ${line.credit}` : "—"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}