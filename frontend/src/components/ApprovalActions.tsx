import type { FC } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Check, X } from "lucide-react";
import { useRole } from "../hooks/useRole";

export const ApprovalActions: FC<{ paymentId: number; status: string }> = ({
  paymentId, status,
}) => {
  const { data: role } = useRole();
  const qc = useQueryClient();

  const approve = useMutation({
    mutationFn: async () => (await api.post(`/payments/${paymentId}/approve/`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] });
    },
  });
  const reject = useMutation({
    mutationFn: async (reason: string) =>
      (await api.post(`/payments/${paymentId}/reject/`, { reason })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] });
    },
  });

  if (!role?.is_finance_manager || status !== "pending") return null;

  const doReject = () => {
    const reason = window.prompt("Reason for rejection?");
    if (reason && reason.trim()) reject.mutate(reason.trim());
  };

  return (
    <div className="flex gap-2">
      <button onClick={() => approve.mutate()} disabled={approve.isPending}
              className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-2 py-1 rounded-md border border-emerald-200 disabled:opacity-50">
        <Check size={14}/> Approve
      </button>
      <button onClick={doReject} disabled={reject.isPending}
              className="inline-flex items-center gap-1 text-xs font-medium text-red-700 bg-red-50 hover:bg-red-100 px-2 py-1 rounded-md border border-red-200 disabled:opacity-50">
        <X size={14}/> Reject
      </button>
    </div>
  );
};
