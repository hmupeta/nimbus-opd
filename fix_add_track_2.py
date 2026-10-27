#!/usr/bin/env python3
"""
fix_add_track_2.py -- Install recharts and create Analytics/Audit/Z-Report features.
"""
from __future__ import annotations
import os
import shutil
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

# Resolve npm to the full path (e.g., npm.cmd)
NPM_PATH = shutil.which("npm")
if not NPM_PATH:
    # Try fallback to portable node if it's not on PATH
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        NPM_PATH = str(node_dir / "npm.cmd")
        ENV["PATH"] = str(node_dir) + os.pathsep + ENV.get("PATH", "")
    else:
        sys.exit("npm not found. Please install Node.js or add the portable nodejs folder to your PATH.")

def sh(*cmd, cwd=None):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV, cwd=cwd or ROOT)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. Install Recharts ───────────────────────────────────────────────
print("==> Installing recharts (frontend)")
sh(NPM_PATH, "install", "recharts", cwd=FRONTEND)

# ─── 2. BACKEND: Create Analytics & Audit Views ────────────────────────
print("==> Creating api/analytics_views.py")
ROOT_API = ROOT / "api"

(ROOT_API / "analytics_views.py").write_text('''\
from datetime import timedelta
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets

from visits.models import Visit
from billing.models import Payment, InvoiceItem
from audit.models import AuditLog
from api.permissions import require_roles
from api.serializers import AuditLogSerializer


class AnalyticsTrendView(APIView):
    permission_classes = [require_roles("admin", "doctor")]
    
    def get(self, request):
        today = timezone.now().date()
        start_date = today - timedelta(days=6)
        
        # 1. Footfall (Last 7 days)
        footfall_qs = Visit.objects.filter(arrived_at__date__gte=start_date) \\
            .annotate(date=TruncDate('arrived_at')) \\
            .values('date') \\
            .annotate(count=Count('id')) \\
            .order_by('date')
            
        footfall_dict = {str(item['date']): item['count'] for item in footfall_qs}
        
        # 2. Revenue Trend (Last 7 days)
        revenue_qs = Payment.objects.filter(paid_at__date__gte=start_date) \\
            .annotate(date=TruncDate('paid_at')) \\
            .values('date') \\
            .annotate(total=Sum('amount')) \\
            .order_by('date')
            
        revenue_dict = {str(item['date']): float(item['total']) for item in revenue_qs}
        
        # 3. Revenue by Category
        category_qs = InvoiceItem.objects.values('category') \\
            .annotate(total=Sum('total')) \\
            .order_by('-total')
            
        # Format for charts
        chart_data = []
        for i in range(7):
            d = start_date + timedelta(days=i)
            d_str = str(d)
            chart_data.append({
                "date": d.strftime("%a"), # Mon, Tue, etc.
                "visits": footfall_dict.get(d_str, 0),
                "revenue": revenue_dict.get(d_str, 0.0)
            })
            
        pie_data = [{"name": item["category"].capitalize(), "value": float(item["total"])} for item in category_qs]

        return Response({
            "trend": chart_data,
            "category_breakdown": pie_data
        })


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [require_roles("admin")]
    
    def get_queryset(self):
        return AuditLog.objects.all().order_by("-at")[:200] # Last 200 actions


class ZReportView(APIView):
    permission_classes = [require_roles("admin", "receptionist")]
    
    def get(self, request):
        today = timezone.now().date()
        # Payments received by THIS user today
        payments = Payment.objects.filter(received_by=request.user, paid_at__date=today)
        
        summary = payments.values('method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        total = payments.aggregate(total=Sum('amount'))['total'] or 0.00
        
        return Response({
            "date": today,
            "cashier": request.user.get_full_name() or request.user.email,
            "summary": list(summary),
            "total_collected": total
        })
''', encoding="utf-8")

# ─── 3. BACKEND: Add AuditLogSerializer ────────────────────────────────
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")
if "class AuditLogSerializer" not in s:
    s += '''

from audit.models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="System")
    model_name = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "at", "user_email", "action", "model_name", "object_id", "before", "after"]
'''
    sp.write_text(s, encoding="utf-8")

# ─── 4. BACKEND: Wire URLs ─────────────────────────────────────────────
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "AnalyticsTrendView" not in u:
    u = u.replace(
        "from .platform_views import PlatformStatsView, PlatformTenantViewSet",
        "from .platform_views import PlatformStatsView, PlatformTenantViewSet\n"
        "from .analytics_views import AnalyticsTrendView, AuditLogViewSet, ZReportView"
    )
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n"
        "    path('analytics/trend/', AnalyticsTrendView.as_view(), name='analytics-trend'),\n"
        "    path('analytics/z-report/', ZReportView.as_view(), name='z-report'),\n"
    )
    u = u.replace(
        'router.register("platform/clinics", PlatformTenantViewSet, basename="platform-clinic")',
        'router.register("platform/clinics", PlatformTenantViewSet, basename="platform-clinic")\n'
        'router.register("audit-logs", AuditLogViewSet, basename="audit-log")'
    )
    up.write_text(u, encoding="utf-8")

# ─── 5. FRONTEND: Update Dashboard with Charts ─────────────────────────
print("==> Updating Dashboard.tsx with Charts")
write_frontend("src/pages/Dashboard.tsx", '''\
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api/client";
import { currentUser } from "../api/auth";
import type { DashboardSummary, Paginated, Visit } from "../api/types";
import PharmacistDashboard from "./PharmacistDashboard";
import LabTechDashboard from "./LabTechDashboard";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ['#0284c7', '#10b981', '#6366f1', '#f59e0b', '#ef4444'];

export default function Dashboard() {
  const user = currentUser();
  
  if (user?.is_platform_admin) return <Navigate to="/platform" replace />;
  if (user?.role === "lab") return <LabTechDashboard />;
  if (user?.role === "pharmacist") return <PharmacistDashboard />;
  if (user?.role === "receptionist") return <Navigate to="/billing" replace />;
  if (user?.role === "radiology") return <Navigate to="/radiology" replace />;

  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get<DashboardSummary>("/reports/dashboard/")).data,
  });

  const visits = useQuery({
    queryKey: ["visits", "active"],
    queryFn: async () => {
      const activeStatuses = ["open", "triaged", "in_consultation"];
      const results = await Promise.all(
        activeStatuses.map((s) =>
          api.get<Paginated<Visit>>(`/visits/?status=${s}`).then((r) => r.data.results)
        )
      );
      return results.flat();
    },
  });

  const analytics = useQuery({
    queryKey: ["analytics", "trend"],
    queryFn: async () => (await api.get("/analytics/trend/")).data,
  });

  const nursingQueue = visits.data?.filter((v) => v.status === "open") || [];
  const doctorQueue = visits.data?.filter((v) => v.status === "triaged" || v.status === "in_consultation") || [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Clinic Dashboard</h1>

      {summary.data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Today's visits" value={summary.data.census.total} />
          <Stat label="Waiting for Nurse" value={nursingQueue.length} />
          <Stat label="Waiting for Doctor" value={doctorQueue.length} />
          <Stat label="Revenue today" value={`ZMW ${summary.data.revenue.today}`} />
        </div>
      )}

      {/* Charts Row */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-white border rounded-lg p-4 md:col-span-2 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Patient Footfall & Revenue (Last 7 Days)</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.data?.trend || []}>
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <YAxis yAxisId="left" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar yAxisId="left" dataKey="visits" fill="#0284c7" radius={[4,4,0,0]} name="Patients" />
                <Bar yAxisId="right" dataKey="revenue" fill="#10b981" radius={[4,4,0,0]} name="Revenue (ZMW)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border rounded-lg p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Revenue Breakdown</h2>
          <div className="h-64 flex items-center justify-center">
            {(analytics.data?.category_breakdown?.length || 0) > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={analytics.data.category_breakdown} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {analytics.data.category_breakdown.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-500 text-sm">No revenue data yet.</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Nursing Queue */}
        <section>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-lg font-semibold text-sky-800">Nursing Queue</h2>
            <span className="bg-sky-100 text-sky-700 text-xs px-2 py-0.5 rounded-full">{nursingQueue.length}</span>
          </div>
          <ul className="divide-y border rounded-lg bg-white">
            {nursingQueue.map((v) => (
              <li key={v.id}>
                <Link to={`/visits/${v.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50">
                  <div>
                    <p className="font-medium">{v.patient_name}</p>
                    <p className="text-sm text-slate-500">{v.visit_no}</p>
                  </div>
                  <span className="text-xs bg-sky-100 text-sky-700 rounded px-2 py-0.5 font-medium">Record Vitals →</span>
                </Link>
              </li>
            ))}
            {nursingQueue.length === 0 && <li className="p-4 text-slate-500 text-sm text-center">No patients waiting.</li>}
          </ul>
        </section>

        {/* Doctor's Queue */}
        <section>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-lg font-semibold text-emerald-800">Doctor's Queue</h2>
            <span className="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded-full">{doctorQueue.length}</span>
          </div>
          <ul className="divide-y border rounded-lg bg-white">
            {doctorQueue.map((v) => (
              <li key={v.id}>
                <Link to={`/visits/${v.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50">
                  <div>
                    <p className="font-medium">{v.patient_name}</p>
                    <p className="text-sm text-slate-500">{v.visit_no}</p>
                  </div>
                  <span className={`text-xs rounded px-2 py-0.5 font-medium ${v.status === 'triaged' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                    {v.status === 'triaged' ? 'Start Consult →' : 'In Consult'}
                  </span>
                </Link>
              </li>
            ))}
            {doctorQueue.length === 0 && <li className="p-4 text-slate-500 text-sm text-center">No patients waiting.</li>}
          </ul>
        </section>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}
''')

# ─── 6. FRONTEND: Create Audit Trail Page ──────────────────────────────
print("==> Creating AuditTrail.tsx")
write_frontend("src/pages/AuditTrail.tsx", '''\
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
''')

# ─── 7. FRONTEND: Add Z-Report to Billing ──────────────────────────────
print("==> Updating BillingDashboard.tsx with Z-Report")
bp = FRONTEND / "src" / "pages" / "BillingDashboard.tsx"
b = bp.read_text(encoding="utf-8")

if "z-report" not in b:
    b = b.replace(
        'const visits = useQuery({',
        '''const zReport = useQuery({
    queryKey: ["z-report"],
    queryFn: async () => (await api.get("/analytics/z-report/")).data,
  });

  const visits = useQuery({'''
    )
    
    b = b.replace(
        '<h1 className="text-2xl font-semibold">Reception / Billing</h1>',
        '''<div className="flex justify-between items-start">
        <h1 className="text-2xl font-semibold">Reception / Billing</h1>
        
        {zReport.data && (
          <div className="bg-white border rounded-lg px-4 py-3 shadow-sm text-sm">
            <span className="text-slate-500 font-medium">My Shift ({zReport.data.date}): </span>
            <span className="font-bold text-emerald-600 ml-1">ZMW {zReport.data.total_collected}</span>
            <span className="text-xs text-slate-400 ml-2">({zReport.data.summary.length} transactions)</span>
          </div>
        )}
      </div>'''
    )
    bp.write_text(b, encoding="utf-8")

# ─── 8. FRONTEND: Routing & Navigation ─────────────────────────────────
print("==> Updating Layout and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Audit Trail" not in l:
    l = l.replace(
        '            {user?.is_platform_admin && (',
        '            {!user?.is_platform_admin && user?.role === "admin" && (\n              <NavLink to="/audit" className={linkClass}>Audit Trail</NavLink>\n            )}\n\n            {user?.is_platform_admin && ('
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")
if "AuditTrail" not in a:
    a = a.replace(
        'import StockDashboard from "./pages/StockDashboard";',
        'import StockDashboard from "./pages/StockDashboard";\nimport AuditTrail from "./pages/AuditTrail";'
    )
    a = a.replace(
        '<Route path="/stock" element={<StockDashboard />} />',
        '<Route path="/stock" element={<StockDashboard />} />\n          <Route path="/audit" element={<AuditTrail />} />'
    )
    ap.write_text(a, encoding="utf-8")

print("==> Done. You must restart the Django server.")