import type { FC } from "react";

const MAP: Record<string, { label: string; cls: string }> = {
  pending:  { label: "Pending Approval", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  approved: { label: "Approved",         cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  rejected: { label: "Rejected",         cls: "bg-red-50 text-red-700 border-red-200" },
};

export const PaymentStatusBadge: FC<{ status?: string; reason?: string | null }> = ({
  status, reason,
}) => {
  const m = MAP[status ?? ""] ?? {
    label: status ?? "—",
    cls: "bg-slate-50 text-slate-700 border-slate-200",
  };
  return (
    <span title={reason || undefined}
          className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full border ${m.cls}`}>
      {m.label}
    </span>
  );
};
