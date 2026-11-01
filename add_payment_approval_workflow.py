#!/usr/bin/env python3
"""
add_payment_approval_workflow.py

Adds Accountant + Finance Manager roles and a maker/checker approval
workflow on billing.Payment.

Safe/defensive:
  - Backend patches are additive and wrapped in try/except where risky.
  - Existing Payment records are backfilled to status='approved' so
    current reports are unaffected.
  - Frontend only *creates* new files; wiring into nav / payments page
    is left as a documented manual step (see end of output).
"""
from __future__ import annotations
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def sh(*cmd, check=True, cwd=ROOT):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=cwd)

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

# ═════════════════════════════════════════════════════════════════════
# 1. api/roles.py — role helpers + DRF permission classes
# ═════════════════════════════════════════════════════════════════════
print("==> Writing api/roles.py")
write("api/roles.py", r'''
"""Role constants, helpers, and DRF permission classes.

Roles are stored in Django Groups so no migration of the User model is
needed. Assign with:  python manage.py assign_role <username> "Accountant"
"""
from rest_framework.permissions import BasePermission

ACCOUNTANT = "Accountant"
FINANCE_MANAGER = "Finance Manager"
ROLE_CHOICES = (ACCOUNTANT, FINANCE_MANAGER)


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return "Admin"
    names = set(user.groups.values_list("name", flat=True))
    if FINANCE_MANAGER in names:
        return FINANCE_MANAGER
    if ACCOUNTANT in names:
        return ACCOUNTANT
    if user.is_staff:
        return "Staff"
    return None


def has_role(user, role):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=role).exists()


class IsAccountant(BasePermission):
    message = "Accountant role required."
    def has_permission(self, request, view):
        return has_role(request.user, ACCOUNTANT)


class IsFinanceManager(BasePermission):
    message = "Finance Manager role required."
    def has_permission(self, request, view):
        return has_role(request.user, FINANCE_MANAGER)


class IsAccountantOrFinanceManager(BasePermission):
    message = "Accountant or Finance Manager role required."
    def has_permission(self, request, view):
        u = request.user
        return (u.is_superuser or has_role(u, ACCOUNTANT)
                or has_role(u, FINANCE_MANAGER))
''')

# ═════════════════════════════════════════════════════════════════════
# 2. Management commands: setup_roles, assign_role
# ═════════════════════════════════════════════════════════════════════
print("\n==> Writing management commands")
write("api/management/__init__.py", "")
write("api/management/commands/__init__.py", "")
write("api/management/commands/setup_roles.py", r'''
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from api.roles import ACCOUNTANT, FINANCE_MANAGER


class Command(BaseCommand):
    help = "Create the Accountant and Finance Manager groups."

    def handle(self, *args, **opts):
        for name in (ACCOUNTANT, FINANCE_MANAGER):
            g, created = Group.objects.get_or_create(name=name)
            self.stdout.write(f"{'created' if created else 'exists '}: {name}")
''')
write("api/management/commands/assign_role.py", r'''
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from api.roles import ROLE_CHOICES


class Command(BaseCommand):
    help = "Assign a role to a user. Usage: assign_role <username> <role>"

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("role", choices=ROLE_CHOICES)

    def handle(self, username, role, *args, **opts):
        U = get_user_model()
        try:
            user = U.objects.get(username=username)
        except U.DoesNotExist:
            raise CommandError(f"No user named {username!r}")
        g = Group.objects.get(name=role)
        user.groups.add(g)
        self.stdout.write(self.style.SUCCESS(f"{username} → {role}"))
''')

# ═════════════════════════════════════════════════════════════════════
# 3. billing/models.py — workflow fields on Payment
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching billing/models.py (Payment workflow fields)")
mp = ROOT / "billing" / "models.py"
src = mp.read_text(encoding="utf-8")

if "approved_by" in src and "created_by" in src:
    print("   Payment already has workflow fields — skipping")
else:
    if "class Payment(" not in src:
        sys.exit("!! Cannot find 'class Payment(' in billing/models.py")

    # Ensure required imports
    if "from django.conf import settings" not in src:
        src = src.replace(
            "from django.db import models",
            "from django.db import models\nfrom django.conf import settings",
            1,
        )
    if "from django.utils import timezone" not in src:
        # Not required by the field declaration, only by the view action
        pass

    # Insert manager + workflow fields right after class Payment(...):
    m = re.search(r"(class Payment\([^)]*\):\s*\n)", src)
    if not m:
        sys.exit("!! Could not locate Payment class declaration")
    inject = (
        '    # ── approval workflow ────────────────────────────────────────\n'
        '    STATUS_CHOICES = [\n'
        '        ("pending",  "Pending Approval"),\n'
        '        ("approved", "Approved"),\n'
        '        ("rejected", "Rejected"),\n'
        '    ]\n'
        '    status = models.CharField(max_length=16, choices=STATUS_CHOICES,\n'
        '                              default="approved", db_index=True)\n'
        '    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,\n'
        '                                   on_delete=models.SET_NULL,\n'
        '                                   related_name="payments_created")\n'
        '    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,\n'
        '                                    on_delete=models.SET_NULL,\n'
        '                                    related_name="payments_approved")\n'
        '    approved_at = models.DateTimeField(null=True, blank=True)\n'
        '    rejection_reason = models.TextField(blank=True, default="")\n'
    )
    src = src[:m.end()] + inject + src[m.end():]
    mp.write_text(src, encoding="utf-8")
    print("   added status/created_by/approved_by/approved_at/rejection_reason")

# Add PaymentManager with .approved() helper, once
if "class PaymentManager" not in src:
    mgr = (
        "\n\nclass PaymentManager(models.Manager):\n"
        "    \"\"\"Report-friendly default manager.\"\"\"\n"
        "    def approved(self):\n"
        "        return self.filter(status='approved')\n\n"
    )
    # Insert *before* class Payment
    src = mp.read_text(encoding="utf-8")
    src = src.replace("class Payment(", mgr + "class Payment(", 1)
    # Attach manager if not already present
    if "objects = PaymentManager()" not in src:
        src = re.sub(
            r"(class Payment\([^)]*\):\s*\n)",
            r"\1    objects = PaymentManager()\n",
            src, count=1,
        )
    mp.write_text(src, encoding="utf-8")
    print("   added PaymentManager with .approved()")

# ═════════════════════════════════════════════════════════════════════
# 4. Migrations + groups
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running makemigrations + migrate")
sh(str(PY), "manage.py", "makemigrations", "billing")
sh(str(PY), "manage.py", "migrate")

print("\n==> Creating role groups")
sh(str(PY), "manage.py", "setup_roles")

# ═════════════════════════════════════════════════════════════════════
# 5. billing/views.py — approve / reject actions (append-only patch)
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching billing/views.py (approve/reject actions)")
vp = ROOT / "billing" / "views.py"
if not vp.exists():
    sys.exit("!! billing/views.py not found")
vsrc = vp.read_text(encoding="utf-8")

PATCH_MARKER = "# === approval-workflow patch ==="
if PATCH_MARKER not in vsrc:
    vsrc += f'''

{PATCH_MARKER}
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

    def _wf_approve(self, request, pk=None):
        p = self.get_object()
        if p.status == "approved":
            return _wf_Response({"detail": "Already approved."},
                                status=_wf_status.HTTP_400_BAD_REQUEST)
        if p.created_by_id == request.user.id and not request.user.is_superuser:
            return _wf_Response(
                {"detail": "You cannot approve your own payment."},
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
        if not hasattr(PaymentViewSet, "perform_create_orig"):
            PaymentViewSet.perform_create_orig = PaymentViewSet.perform_create
        PaymentViewSet.perform_create = _wf_perform_create
        PaymentViewSet.approve = _wf_action(
            detail=True, methods=["post"], permission_classes=[_IsFM])(_wf_approve)
        PaymentViewSet.reject = _wf_action(
            detail=True, methods=["post"], permission_classes=[_IsFM])(_wf_reject)
        print("[approval-workflow] approve/reject actions registered.")
    else:
        print("[approval-workflow] WARNING: PaymentViewSet not found — patch skipped.")
except Exception as _e:  # noqa: BLE001
    import logging
    logging.getLogger(__name__).warning(f"[approval-workflow] patch failed: {_e}")
'''
    vp.write_text(vsrc, encoding="utf-8")
    print("   appended approve/reject patch")
else:
    print("   views.py already patched — skipping")

# ═════════════════════════════════════════════════════════════════════
# 6. Reports: only approved payments count
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching api/accounting_reports.py (use approved payments only)")
rp = ROOT / "api" / "accounting_reports.py"
if rp.exists():
    r = rp.read_text(encoding="utf-8")
    if "Payment.objects.approved()" in r:
        print("   already filtered — skipping")
    elif "Payment.objects." in r:
        # Replace every Payment.objects.<...> with Payment.objects.approved().<...>
        # Guard against double-application
        r = re.sub(r"Payment\.objects\.(?!approved\()", "Payment.objects.approved().", r)
        rp.write_text(r, encoding="utf-8")
        print("   rewrote Payment.objects.* → Payment.objects.approved().*")
    else:
        print("   (no Payment.objects.* found — nothing to do)")
else:
    print("   api/accounting_reports.py not found — skipping")

# ═════════════════════════════════════════════════════════════════════
# 7. /api/auth/role/ endpoint (new, additive — no existing view touched)
# ═════════════════════════════════════════════════════════════════════
print("\n==> Adding /api/auth/role/ endpoint")
write("api/auth_role.py", r'''
"""Exposes the current user's role. Additive — does not touch existing auth views."""
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

# Find a urls.py to hook into — try api/urls.py first, then project urls
urls_candidates = [
    ROOT / "api" / "urls.py",
    ROOT / "opd" / "urls.py",
    ROOT / "config" / "urls.py",
]
urls_patched = False
for uc in urls_candidates:
    if not uc.exists():
        continue
    usrc = uc.read_text(encoding="utf-8")
    if "auth/role/" in usrc:
        print(f"   {uc.relative_to(ROOT)} already has /auth/role/")
        urls_patched = True
        break
    # Add import + path
    if "from api.auth_role import RoleView" not in usrc:
        # Ensure rest_framework import isn't needed here — we import inline
        if "from api.auth_role import RoleView" not in usrc:
            usrc = usrc.replace(
                "from django.urls import path",
                "from django.urls import path\nfrom api.auth_role import RoleView",
                1,
            ) if "from django.urls import path" in usrc else usrc
            # If pattern wasn't matched, inject import above first urlpatterns
            if "from api.auth_role import RoleView" not in usrc:
                usrc = usrc.replace(
                    "urlpatterns",
                    "from api.auth_role import RoleView\nurlpatterns",
                    1,
                )
    if "path(\"auth/role/\"" not in usrc and "path('auth/role/'" not in usrc:
        # Insert as first entry in urlpatterns = [ ... ]
        usrc = re.sub(
            r"(urlpatterns\s*=\s*\[\s*)",
            r'\1path("auth/role/", RoleView.as_view(), name="auth-role"),\n    ',
            usrc, count=1,
        )
    uc.write_text(usrc, encoding="utf-8")
    print(f"   patched {uc.relative_to(ROOT)} with /auth/role/")
    urls_patched = True
    break

if not urls_patched:
    print("   !! Could not find a urls.py to hook into. Add this manually:")
    print('      from api.auth_role import RoleView')
    print('      path("auth/role/", RoleView.as_view(), name="auth-role"),')

# ═════════════════════════════════════════════════════════════════════
# 8. Quick backend sanity check
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running Django system checks")
sh(str(PY), "manage.py", "check")

# ═════════════════════════════════════════════════════════════════════
# 9. Frontend: new files only (safe/additive)
# ═════════════════════════════════════════════════════════════════════
print("\n==> Creating frontend role hook + components")

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

type Status = "pending" | "approved" | "rejected" | string;

const MAP: Record<string, { label: string; cls: string }> = {
  pending:  { label: "Pending Approval", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  approved: { label: "Approved",         cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  rejected: { label: "Rejected",         cls: "bg-red-50 text-red-700 border-red-200" },
};

export const PaymentStatusBadge: FC<{ status: Status; reason?: string | null }> = ({
  status, reason,
}) => {
  const m = MAP[status] ?? { label: status, cls: "bg-slate-50 text-slate-700 border-slate-200" };
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

interface Props { paymentId: number; status: string; }

export const ApprovalActions: FC<Props> = ({ paymentId, status }) => {
  const { data: role } = useRole();
  const qc = useQueryClient();

  const approve = useMutation({
    mutationFn: async () => (await api.post(`/payments/${paymentId}/approve/`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payments"] }),
  });
  const reject = useMutation({
    mutationFn: async (reason: string) =>
      (await api.post(`/payments/${paymentId}/reject/`, { reason })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payments"] }),
  });

  if (!role?.is_finance_manager || status !== "pending") return null;

  const doReject = () => {
    const reason = window.prompt("Reason for rejection?");
    if (reason && reason.trim()) reject.mutate(reason.trim());
  };

  return (
    <div className="flex gap-2">
      <button onClick={() => approve.mutate()} disabled={approve.isPending}
              className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-2 py-1 rounded-md border border-emerald-200">
        <Check size={14}/> Approve
      </button>
      <button onClick={doReject} disabled={reject.isPending}
              className="inline-flex items-center gap-1 text-xs font-medium text-red-700 bg-red-50 hover:bg-red-100 px-2 py-1 rounded-md border border-red-200">
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
    queryFn: async () => (await api.get("/payments/", { params: { status: "pending" } })).data,
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
                  <td className="px-4 py-3">{p.patient_name || p.patient || p.reference || `#${p.id}`}</td>
                  <td className="px-4 py-3 text-right font-medium">ZMW {p.amount}</td>
                  <td className="px-4 py-3"><PaymentStatusBadge status={p.status} /></td>
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
# 10. Vite build to verify
# ═════════════════════════════════════════════════════════════════════
import shutil as _sh
npm = _sh.which("npm")
if not npm:
    for cand in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if cand.exists():
            npm = str(cand); break

if npm:
    print("\n==> Running Vite build to verify")
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
else:
    print("\n   (npm not found — skipping Vite build)")

# ═════════════════════════════════════════════════════════════════════
# 11. Commit + push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(
        ["git", "commit", "-m",
         "feat(payments): Accountant/Finance Manager maker-checker approval workflow"],
        cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS (manual — required to finish wiring):")
print("  1. Assign roles to your users (run twice):")
print('       python manage.py assign_role <accountant_username> "Accountant"')
print('       python manage.py assign_role <fm_username> "Finance Manager"')
print("  2. Add <Approvals /> to your router (e.g. src/App.tsx or src/routes.tsx):")
print('       import Approvals from "./pages/Approvals";')
print('       <Route path="/approvals" element={<Approvals />} />')
print("  3. In your sidebar/nav, show the Approvals link only when")
print('       useRole().data?.is_finance_manager === true')
print("  4. In your existing Payments list, drop in:")
print('       import { PaymentStatusBadge } from "../components/PaymentStatusBadge";')
print('       import { ApprovalActions }     from "../components/ApprovalActions";')
print('       ... <PaymentStatusBadge status={p.status} /> ...')
print('       ... <ApprovalActions paymentId={p.id} status={p.status} /> ...')
print("  5. On Render: Manual Deploy → Clear build cache for BOTH backend + frontend.")