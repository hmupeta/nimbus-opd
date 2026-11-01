#!/usr/bin/env python3
"""
finish_payment_approval.py

Continuation of add_payment_approval_workflow.py (which crashed on an
f-string bug at step 6). Safe to re-run.

Verifies steps 1-5 from the previous run, then completes:
  6.  billing/views.py     – approve/reject actions + status filter
  7.  billing/serializers.py – expose workflow fields
  8.  api/accounting_reports.py – count only approved payments
  9.  api/auth_role.py + urls hook – /api/auth/role/
  10. frontend hook, badge, actions, Approvals page
  11. Vite build → commit → push
"""
from __future__ import annotations
import os, re, subprocess, sys, shutil
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def sh(*cmd, cwd=ROOT, check=True, quiet=False):
    if not quiet:
        print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=cwd, check=check,
                          capture_output=quiet, text=quiet)

def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"   wrote {rel}")

def write_fe(rel, content):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"   wrote frontend/{rel}")

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

# ═════════════════════════════════════════════════════════════════════
# 0. Verify prior run finished steps 1-5
# ═════════════════════════════════════════════════════════════════════
print("==> Verifying state from previous run")
checks = {
    "billing/models.py has workflow fields":
        "approved_by" in (ROOT / "billing" / "models.py").read_text(encoding="utf-8"),
    "api/roles.py exists":        (ROOT / "api" / "roles.py").exists(),
    "setup_roles command exists": (ROOT / "api" / "management" / "commands" / "setup_roles.py").exists(),
    "migration 0006 exists":      any((ROOT / "billing" / "migrations").glob("0006_*.py")),
}
ok = True
for desc, cond in checks.items():
    print(f"   {'✓' if cond else '✗'} {desc}")
    ok &= cond
if not ok:
    sys.exit("!! Previous run did not complete. Re-run add_payment_approval_workflow.py "
             "after fixing the f-string bug, OR run from a clean state.")

# ═════════════════════════════════════════════════════════════════════
# 1. billing/views.py — the step that crashed
#    NOTE: patch body is a *raw* string, concatenated with the marker —
#    never an f-string, so JSON braces in the body are safe.
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching billing/views.py")
vp = ROOT / "billing" / "views.py"
vsrc = vp.read_text(encoding="utf-8")
MARKER = "# === approval-workflow patch (v2) ==="

if MARKER in vsrc:
    print("   already patched — skipping")
else:
    BODY = r'''

try:
    from rest_framework.decorators import action as _wf_action
    from rest_framework.response import Response as _wf_Response
    from rest_framework import status as _wf_status
    from rest_framework.exceptions import PermissionDenied as _wf_Deny
    from django.utils import timezone as _wf_tz
    from api.roles import (IsFinanceManager as _IsFM,
                           ACCOUNTANT as _ACCT,
                           FINANCE_MANAGER as _FM,
                           has_role as _has_role)

    def _wf_perform_create(self, serializer):
        u = self.request.user
        if not (u.is_superuser or _has_role(u, _ACCT) or _has_role(u, _FM)):
            raise _wf_Deny("Only Accountant or Finance Manager can create payments.")
        serializer.save(created_by=u, status="pending")

    def _wf_perform_update(self, serializer):
        for k in ("status", "approved_by", "approved_at",
                  "created_by", "rejection_reason"):
            serializer.validated_data.pop(k, None)
        serializer.save()

    def _wf_approve(self, request, pk=None):
        p = self.get_object()
        if p.status == "approved":
            return _wf_Response({"detail": "Already approved."},
                                status=_wf_status.HTTP_400_BAD_REQUEST)
        if p.created_by_id == request.user.id and not request.user.is_superuser:
            return _wf_Response(
                {"detail": "You cannot approve a payment you created."},
                status=_wf_status.HTTP_400_BAD_REQUEST)
        p.status = "approved"
        p.approved_by = request.user
        p.approved_at = _wf_tz.now()
        p.rejection_reason = ""
        p.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason"])
        return _wf_Response({"detail": "Approved.", "status": p.status})

    def _wf_reject(self, request, pk=None):
        p = self.get_object()
        if p.status == "rejected":
            return _wf_Response({"detail": "Already rejected."},
                                status=_wf_status.HTTP_400_BAD_REQUEST)
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return _wf_Response({"detail": "A rejection reason is required."},
                                status=_wf_status.HTTP_400_BAD_REQUEST)
        p.status = "rejected"
        p.approved_by = request.user
        p.approved_at = _wf_tz.now()
        p.rejection_reason = reason
        p.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason"])
        return _wf_Response({"detail": "Rejected.", "status": p.status})

    if "PaymentViewSet" in globals():
        _P = PaymentViewSet
        if not hasattr(_P, "_wf_original_get_queryset"):
            _P._wf_original_get_queryset = _P.get_queryset

        def _wf_get_queryset(self):
            qs = _P._wf_original_get_queryset(self)
            s = self.request.query_params.get("status")
            if s in ("pending", "approved", "rejected"):
                qs = qs.filter(status=s)
            return qs

        _P.perform_create  = _wf_perform_create
        _P.perform_update  = _wf_perform_update
        _P.get_queryset    = _wf_get_queryset
        _P.approve = _wf_action(detail=True, methods=["post"],
                                permission_classes=[_IsFM])(_wf_approve)
        _P.reject  = _wf_action(detail=True, methods=["post"],
                                permission_classes=[_IsFM])(_wf_reject)
    else:
        import logging
        logging.getLogger(__name__).warning(
            "[approval-workflow] PaymentViewSet not found in billing/views.py.")
except Exception as _e:
    import logging
    logging.getLogger(__name__).warning(
        f"[approval-workflow] patch failed: {_e}")
'''
    vsrc += "\n\n" + MARKER + BODY
    vp.write_text(vsrc, encoding="utf-8")
    print("   appended approve/reject/queryset patch")

# ═════════════════════════════════════════════════════════════════════
# 2. billing/serializers.py — expose workflow fields
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching billing/serializers.py")
sp = ROOT / "billing" / "serializers.py"
if sp.exists():
    s = sp.read_text(encoding="utf-8")
    if "class PaymentSerializer" not in s:
        print("   [WARN] PaymentSerializer not found — skipping")
    elif '"rejection_reason"' in s or "'rejection_reason'" in s:
        print("   already has workflow fields — skipping")
    elif 'fields = "__all__"' in s or "fields = '__all__'" in s:
        print("   uses __all__ — new fields auto-exposed")
    else:
        m = re.search(
            r"(class PaymentSerializer\b[\s\S]{0,3000}?fields\s*=\s*\[)([^\]]*?)(\])",
            s,
        )
        if m:
            prefix, body, suffix = m.groups()
            add = ('\n            "status", "created_by", "approved_by", '
                   '"approved_at", "rejection_reason",\n        ')
            new = prefix + body.rstrip().rstrip(",") + add + suffix
            s = s[:m.start()] + new + s[m.end():]
            sp.write_text(s, encoding="utf-8")
            print("   appended workflow fields to PaymentSerializer.Meta.fields")
        else:
            print("   [WARN] Could not locate Meta.fields list — add manually:")
            print('       "status", "created_by", "approved_by", "approved_at", "rejection_reason",')

# ═════════════════════════════════════════════════════════════════════
# 3. api/accounting_reports.py — approved-only reads
#    Only touch *read* methods; never .create / .update / .bulk_create.
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching api/accounting_reports.py")
rp = ROOT / "api" / "accounting_reports.py"
READ_METHODS = ("filter", "all", "get", "aggregate", "values", "values_list",
                "annotate", "count", "exclude", "first", "last", "order_by",
                "exists", "distinct", "none", "only", "defer")
if rp.exists():
    r = rp.read_text(encoding="utf-8")
    if "Payment.objects.approved()" in r:
        print("   already filtered — skipping")
    else:
        pat = re.compile(
            r"Payment\.objects\.(" + "|".join(READ_METHODS) + r")\b"
        )
        new_r, n = pat.subn(r"Payment.objects.approved().\1", r)
        if n:
            rp.write_text(new_r, encoding="utf-8")
            print(f"   rewrote {n} read-only Payment.objects.<m>() → approved()")
        else:
            print("   no read-only Payment.objects.<m>() calls found — no change")
else:
    print("   api/accounting_reports.py not found — skipping")

# ═════════════════════════════════════════════════════════════════════
# 4. /api/auth/role/
# ═════════════════════════════════════════════════════════════════════
print("\n==> Adding /api/auth/role/")
write("api/auth_role.py", r'''
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api.roles import get_user_role, has_role, ACCOUNTANT, FINANCE_MANAGER


class RoleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            "role": get_user_role(u),
            "is_accountant": has_role(u, ACCOUNTANT),
            "is_finance_manager": has_role(u, FINANCE_MANAGER),
            "username": u.get_username(),
            "is_superuser": u.is_superuser,
        })
''')

urls_patched = False
for uc in [ROOT / "api" / "urls.py", ROOT / "opd" / "urls.py",
           ROOT / "config" / "urls.py"]:
    if not uc.exists():
        continue
    usrc = uc.read_text(encoding="utf-8")
    if "auth/role/" in usrc:
        print(f"   {uc.relative_to(ROOT)} already has /auth/role/")
        urls_patched = True
        break
    if "from api.auth_role import RoleView" not in usrc:
        if "from django.urls import path" in usrc:
            usrc = usrc.replace(
                "from django.urls import path",
                "from django.urls import path\nfrom api.auth_role import RoleView",
                1,
            )
        else:
            usrc = usrc.replace(
                "urlpatterns",
                "from api.auth_role import RoleView\nurlpatterns",
                1,
            )
    usrc = re.sub(
        r"(urlpatterns\s*=\s*\[\s*)",
        r'\1path("auth/role/", RoleView.as_view(), name="auth-role"),\n    ',
        usrc, count=1,
    )
    uc.write_text(usrc, encoding="utf-8")
    print(f"   patched {uc.relative_to(ROOT)}")
    urls_patched = True
    break

if not urls_patched:
    print("   [WARN] No urls.py found. Add manually:")
    print('       from api.auth_role import RoleView')
    print('       path("auth/role/", RoleView.as_view(), name="auth-role"),')

# ═════════════════════════════════════════════════════════════════════
# 5. Frontend files
# ═════════════════════════════════════════════════════════════════════
print("\n==> Creating frontend files")
write_fe("src/hooks/useRole.ts", r'''
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export type Role = "Accountant" | "Finance Manager" | "Admin" | "Staff" | null;

export interface RoleInfo {
  role: Role;
  is_accountant: boolean;
  is_finance_manager: boolean;
  is_superuser: boolean;
  username: string;
}

export function useRole() {
  return useQuery<RoleInfo>({
    queryKey: ["auth-role"],
    queryFn: async () => (await api.get("/auth/role/")).data,
    staleTime: 5 * 60 * 1000,
  });
}
''')

write_fe("src/components/PaymentStatusBadge.tsx", r'''
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
''')

write_fe("src/components/ApprovalActions.tsx", r'''
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
''')

write_fe("src/pages/Approvals.tsx", r'''
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
''')

# ═════════════════════════════════════════════════════════════════════
# 6. Django check
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running Django system checks")
try:
    sh(str(PY), "manage.py", "check")
except subprocess.CalledProcessError:
    sys.exit("!! Django check failed — fix the above before deploying")

# ═════════════════════════════════════════════════════════════════════
# 7. Vite build
# ═════════════════════════════════════════════════════════════════════
npm = npm_path()
if not npm:
    print("\n[WARN] npm not found — skipping Vite build")
else:
    print("\n==> Running Vite build")
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND,
                       capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ build OK")
    else:
        print("   ❌ build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-20:]:
            print("     " + line)
        sys.exit(1)

# ═════════════════════════════════════════════════════════════════════
# 8. Commit + push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Committing and pushing")
sh("git", "add", ".")
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
if status:
    sh("git", "commit", "-m",
       "feat(payments): accountant/finance-manager maker-checker approval workflow")
else:
    print("   (nothing to commit)")
sh("git", "push", "origin", "main")

print("\n✅ Done.")
print("\nNEXT STEPS:")
print('  1. Assign roles (run once per user):')
print('       python manage.py assign_role <acct_username> "Accountant"')
print('       python manage.py assign_role <fm_username>   "Finance Manager"')
print("  2. Wire Approvals page into your router and add badge/actions to Payments list")
print("     (see the manual-wiring notes in my previous message).")
print("  3. On Render: Clear build cache & deploy BOTH backend and frontend.")