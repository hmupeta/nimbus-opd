import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ApprovalActions } from "../components/ApprovalActions";
import { PaymentStatusBadge } from "../components/PaymentStatusBadge";
import { useRole } from "../hooks/useRole";

export default function Approvals() {
  const { data: role } = useRole();
  const { data, isLoading } = useQuery({
    queryKey: ["payments", "pending"],
    queryFn: async () =>
      (await api.get("/payments/", { params: { status: "pending" } })).data,
    enabled: !!role?.is_finance_manager,
  });

  if (!role?.is_finance_manager) {
    return (
      <div className="p-8 text-sm text-slate-500">
        This page is only available to the Finance Manager.
      </div>
    );
  }

  const rows = Array.isArray(data) ? data : (data?.results ?? []);

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Payment Approvals</h1>
        <p className="text-sm text-slate-500 mt-1">
          Review and approve payments initiated by the Accountant.
        </p>
      </div>

      <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-6 text-sm text-slate-500">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-sm text-slate-500">No pending payments. 🎉</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Patient / Ref</th>
                <th className="text-right px-4 py-3">Amount</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((p: any) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">{p.date || p.created_at || "—"}</td>
                  <td className="px-4 py-3">
                    {p.patient_name || p.patient || p.reference || `#${p.id}`}
                  </td>
                  <td className="px-4 py-3 text-right font-medium">ZMW {p.amount}</td>
                  <td className="px-4 py-3">
                    <PaymentStatusBadge status={p.status} reason={p.rejection_reason} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end">
                      <ApprovalActions paymentId={p.id} status={p.status} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
