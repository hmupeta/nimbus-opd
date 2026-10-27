#!/usr/bin/env python3
"""
add_platform_admin.py -- Add Platform Admin Dashboard (Stats, Approvals, Impersonation).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

FRONTEND = ROOT / "frontend"
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Update JWT Payload ────────────────────────────────────
print("==> Patching api/auth.py (Add is_platform_admin claim)")
ap = ROOT / "api" / "auth.py"
a = ap.read_text(encoding="utf-8")
if 'token["is_platform_admin"]' not in a:
    a = a.replace(
        'token["role"] = user.role',
        'token["role"] = user.role\n        token["is_platform_admin"] = user.is_platform_admin'
    )
    ap.write_text(a, encoding="utf-8")

# ─── 2. BACKEND: Create Platform Views ─────────────────────────────────
print("==> Creating api/platform_views.py")
pv_path = ROOT / "api" / "platform_views.py"
pv_path.write_text('''\
from django.db.models import Count, Sum, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from tenants.models import Tenant, User
from api.auth import TenantTokenObtainPairSerializer
from api.serializers import TenantSerializer


class PlatformPermission(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and getattr(request.user, "is_platform_admin", False)


class PlatformStatsView(APIView):
    permission_classes = [PlatformPermission]

    def get(self, request):
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(is_active=True).count()
        pending_tenants = Tenant.objects.filter(is_active=False).count()
        
        # Mock MRR calculation: Assume all active tenants are on the Pro plan (K3,500/mo)
        mrr = active_tenants * 3500

        return Response({
            "total_clinics": total_tenants,
            "active_clinics": active_tenants,
            "pending_clinics": pending_tenants,
            "mrr_zmw": mrr,
        })


class PlatformTenantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tenant.objects.all().order_by("-created_at")
    serializer_class = TenantSerializer
    permission_classes = [PlatformPermission]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        tenant = self.get_object()
        tenant.is_active = True
        tenant.save(update_fields=["is_active"])
        return Response({"detail": "Clinic approved and activated successfully."})

    @action(detail=True, methods=["post"])
    def impersonate(self, request, pk=None):
        tenant = self.get_object()
        # Find the primary admin for this tenant
        admin = User.objects.filter(tenant=tenant, role="admin").first()
        if not admin:
            return Response({"detail": "No admin user found for this clinic."}, status=status.HTTP_404_NOT_FOUND)

        # Generate tokens manually
        refresh = RefreshToken.for_user(admin)
        # Inject custom claims exactly like our custom serializer does
        refresh["tenant_id"] = str(admin.tenant_id)
        refresh["role"] = admin.role
        refresh["email"] = admin.email
        refresh["full_name"] = admin.get_full_name() or admin.email
        refresh["is_platform_admin"] = False # Impersonated session is not platform admin

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "clinic_name": tenant.name
        })
''', encoding="utf-8")

# ─── 3. BACKEND: Wire URL ──────────────────────────────────────────────
print("==> Patching api/urls.py")
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "PlatformTenantViewSet" not in u:
    u = u.replace(
        "from .views import (",
        "from .platform_views import PlatformStatsView, PlatformTenantViewSet\nfrom .views import ("
    )
    u = u.replace(
        'router.register("tenants", TenantViewSet, basename="tenant")',
        'router.register("tenants", TenantViewSet, basename="tenant")\n'
        'router.register("platform/clinics", PlatformTenantViewSet, basename="platform-clinic")'
    )
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n    path('platform/stats/', PlatformStatsView.as_view(), name='platform-stats'),"
    )
    up.write_text(u, encoding="utf-8")

# ─── 4. FRONTEND: Update Auth Types ────────────────────────────────────
print("==> Updating src/api/auth.ts")
at = FRONTEND / "src" / "api" / "auth.ts"
a = at.read_text(encoding="utf-8")
if "is_platform_admin" not in a:
    a = a.replace(
        "  exp: number;\n}",
        "  exp: number;\n  is_platform_admin: boolean;\n}"
    )
    at.write_text(a, encoding="utf-8")

# ─── 5. FRONTEND: Create PlatformAdminDashboard ────────────────────────
print("==> Creating PlatformAdminDashboard.tsx")
write_frontend("src/pages/PlatformAdminDashboard.tsx", '''\
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, setTokens } from "../api/client";
import type { Paginated, DashboardSummary } from "../api/types";

export default function PlatformAdminDashboard() {
  const qc = useQueryClient();
  const nav = useNavigate();

  const stats = useQuery({
    queryKey: ["platform-stats"],
    queryFn: async () => (await api.get("/platform/stats/")).data,
  });

  const clinics = useQuery({
    queryKey: ["platform-clinics"],
    queryFn: async () => (await api.get<Paginated<any>>("/platform/clinics/")).data.results,
  });

  const approve = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/platform/clinics/${id}/approve/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform-clinics"] });
      qc.invalidateQueries({ queryKey: ["platform-stats"] });
    },
  });

  const impersonate = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post(`/platform/clinics/${id}/impersonate/`);
      return data;
    },
    onSuccess: (data) => {
      // Swap the local storage tokens to the impersonated user
      setTokens(data.access, data.refresh);
      // Force a hard reload to re-bind the new tenant context
      window.location.href = "/dashboard";
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-800">SaaS Platform Administration</h1>

      {stats.data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Total Clinics" value={stats.data.total_clinics} />
          <Stat label="Active Clinics" value={stats.data.active_clinics} color="text-emerald-600" />
          <Stat label="Pending Approval" value={stats.data.pending_clinics} color="text-amber-600" />
          <Stat label="MRR (Est.)" value={`K ${stats.data.mrr_zmw.toLocaleString()}`} />
        </div>
      )}

      <div className="bg-white border rounded-lg overflow-hidden">
        <div className="bg-slate-50 px-4 py-3 border-b font-semibold text-slate-700">Registered Clinics</div>
        <table className="w-full text-sm">
          <thead className="text-slate-500 bg-white">
            <tr>
              <th className="text-left px-4 py-2">Clinic Name</th>
              <th className="text-left px-4 py-2">Code</th>
              <th className="text-left px-4 py-2">Status</th>
              <th className="text-left px-4 py-2">Joined</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {clinics.data?.map((c: any) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{c.name}</td>
                <td className="px-4 py-3 font-mono text-xs">{c.code}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${c.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {c.is_active ? "Active" : "Pending"}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500">{new Date(c.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-right space-x-2">
                  {!c.is_active && (
                    <button onClick={() => approve.mutate(c.id)} disabled={approve.isPending} className="bg-emerald-600 text-white text-xs px-3 py-1.5 rounded hover:bg-emerald-700">
                      Approve
                    </button>
                  )}
                  {c.is_active && (
                    <button onClick={() => impersonate.mutate(c.id)} disabled={impersonate.isPending} className="bg-sky-100 text-sky-700 text-xs px-3 py-1.5 rounded hover:bg-sky-200 font-medium">
                      Login as Admin
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, color = "text-slate-800" }: { label: string, value: string | number, color?: string }) {
  return (
    <div className="bg-white border rounded-lg p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}
''')

# ─── 6. FRONTEND: Navigation & Routing ─────────────────────────────────
print("==> Updating Layout and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Platform Admin" not in l:
    l = l.replace(
        '{user ? (',
        '''{user?.is_platform_admin && (
              <NavLink to="/platform" className={linkClass}>Platform Admin</NavLink>
            )}
            {user ? ('''
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")
if "PlatformAdminDashboard" not in a:
    a = a.replace(
        'import Dashboard from "./pages/Dashboard";',
        'import Dashboard from "./pages/Dashboard";\nimport PlatformAdminDashboard from "./pages/PlatformAdminDashboard";'
    )
    a = a.replace(
        '<Route path="/dashboard" element={<Dashboard />} />',
        '<Route path="/dashboard" element={<Dashboard />} />\n          <Route path="/platform" element={<PlatformAdminDashboard />} />'
    )
    ap.write_text(a, encoding="utf-8")

print("==> Done. Refresh your browser.")