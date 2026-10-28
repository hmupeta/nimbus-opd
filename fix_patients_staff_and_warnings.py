#!/usr/bin/env python3
"""
fix_patients_staff_and_warnings.py
  - Overwrites Layout.tsx and App.tsx to guarantee Staff UI appears.
  - Updates Patients.tsx to show exact backend error messages.
  - Fixes DRF pagination warnings on the backend.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

FRONTEND = OPD / "frontend"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Fix Pagination Warnings ───────────────────────────────
print("==> Patching api/views.py (Fixing UnorderedObjectListWarning)")
vp = OPD / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Fix UserViewSet
v = v.replace(
    "qs = User.objects.filter(tenant=t)\n        role = self.request.query_params.get(\"role\")",
    "qs = User.objects.filter(tenant=t).order_by(\"-id\")\n        role = self.request.query_params.get(\"role\")"
)

# Fix PatientViewSet
v = v.replace(
    "qs = Patient.objects.all()\n        q = self.request.query_params.get(\"q\")",
    "qs = Patient.objects.all().order_by(\"-id\")\n        q = self.request.query_params.get(\"q\")"
)

vp.write_text(v, encoding="utf-8")
print("   patched api/views.py")

# ─── 2. FRONTEND: Guarantee Staff Tab in Layout ────────────────────────
print("==> Overwriting src/components/Layout.tsx")
write_frontend("src/components/Layout.tsx", '''\
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { currentUser, logout } from "../api/auth";

export default function Layout() {
  const nav = useNavigate();
  const user = currentUser();

  function handleLogout() { logout(); nav("/login"); }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium ${
      isActive ? "bg-sky-100 text-sky-700" : "text-slate-600 hover:bg-slate-100"
    }`;

  const isClinicalStaff = !user?.is_platform_admin;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200 no-print">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6">
          <Link to="/dashboard" className="text-lg font-bold text-sky-700">OPD</Link>
          <nav className="flex gap-1 overflow-x-auto">
            {isClinicalStaff && <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>}
            {isClinicalStaff && <NavLink to="/patients" className={linkClass}>Patients</NavLink>}
            
            {isClinicalStaff && (user?.role === "receptionist" || user?.role === "admin") && (
              <NavLink to="/appointments" className={linkClass}>Appointments</NavLink>
            )}

            {isClinicalStaff && (user?.role === "lab" || user?.role === "admin") && (
              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>
            )}

            {isClinicalStaff && (user?.role === "radiology" || user?.role === "admin") && (
              <NavLink to="/radiology" className={linkClass}>Radiology</NavLink>
            )}

            {isClinicalStaff && (user?.role === "pharmacist" || user?.role === "admin") && (
              <NavLink to="/pharmacy" className={linkClass}>Pharmacy</NavLink>
            )}

            {isClinicalStaff && (user?.role === "pharmacist" || user?.role === "admin") && (
              <NavLink to="/stock" className={linkClass}>Stock</NavLink>
            )}

            {isClinicalStaff && (user?.role === "receptionist" || user?.role === "admin") && (
              <NavLink to="/billing" className={linkClass}>Billing</NavLink>
            )}

            {isClinicalStaff && user?.role === "admin" && (
              <>
                <NavLink to="/staff" className={linkClass}>Staff</NavLink>
                <NavLink to="/reports" className={linkClass}>MIS Reports</NavLink>
                <NavLink to="/audit" className={linkClass}>Audit Trail</NavLink>
              </>
            )}

            {user?.is_platform_admin && (
              <NavLink to="/platform" className={linkClass}>Platform Admin</NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-slate-600 shrink-0">
            {user ? (
              <>
                <span className="hidden md:inline">{user.full_name || user.email}</span>
                <span className="text-xs bg-slate-100 px-2 py-0.5 rounded capitalize">{user.role}</span>
                <button onClick={handleLogout} className="px-3 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200">
                  Sign out
                </button>
              </>
            ) : (
              <Link to="/login" className="text-sky-700 font-medium">Sign in</Link>
            )}
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
''')

# ─── 3. FRONTEND: Guarantee Staff Route in App.tsx ─────────────────────
print("==> Overwriting src/App.tsx")
write_frontend("src/App.tsx", '''\
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import LandingPage from "./pages/LandingPage";
import WaitingRoom from "./pages/WaitingRoom";
import PatientPortal from "./pages/PatientPortal";
import Dashboard from "./pages/Dashboard";
import Patients from "./pages/Patients";
import PatientDetail from "./pages/PatientDetail";
import VisitTimeline from "./pages/VisitTimeline";
import LabDashboard from "./pages/LabDashboard";
import RadiologyDashboard from "./pages/RadiologyDashboard";
import PharmacyDashboard from "./pages/PharmacyDashboard";
import StockDashboard from "./pages/StockDashboard";
import BillingDashboard from "./pages/BillingDashboard";
import Appointments from "./pages/Appointments";
import AuditTrail from "./pages/AuditTrail";
import MISReports from "./pages/MISReports";
import Staff from "./pages/Staff";
import PlatformAdminDashboard from "./pages/PlatformAdminDashboard";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<Login />} />
      <Route path="/display" element={<WaitingRoom />} />
      <Route path="/portal" element={<PatientPortal />} />
      
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
          <Route path="/visits/:id" element={<VisitTimeline />} />
          <Route path="/appointments" element={<Appointments />} />
          <Route path="/lab" element={<LabDashboard />} />
          <Route path="/radiology" element={<RadiologyDashboard />} />
          <Route path="/pharmacy" element={<PharmacyDashboard />} />
          <Route path="/stock" element={<StockDashboard />} />
          <Route path="/billing" element={<BillingDashboard />} />
          <Route path="/audit" element={<AuditTrail />} />
          <Route path="/reports" element={<MISReports />} />
          <Route path="/staff" element={<Staff />} />
          <Route path="/platform" element={<PlatformAdminDashboard />} />
        </Route>
      </Route>
      
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
''')

# ─── 4. FRONTEND: Show Errors on Patient Creation ──────────────────────
print("==> Updating src/pages/Patients.tsx (Show API Errors)")
pp = FRONTEND / "src" / "pages" / "Patients.tsx"
p_content = pp.read_text(encoding="utf-8")

# Add error state
if "const [formError, setFormError]" not in p_content:
    p_content = p_content.replace(
        "const [showForm, setShowForm] = useState(false);",
        "const [showForm, setShowForm] = useState(false);\n  const [formError, setFormError] = useState<string | null>(null);"
    )

# Update mutation to catch error
p_content = p_content.replace(
    '''  const createPatient = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post<Patient>("/patients/", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      setShowForm(false);
      setFormDob("");
    },
  });''',
    '''  const createPatient = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post<Patient>("/patients/", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      setShowForm(false);
      setFormDob("");
      setFormError(null);
    },
    onError: (err: any) => {
      const data = err.response?.data;
      if (typeof data === "object") {
        const messages = Object.entries(data).map(([k, v]) => `${k}: ${v}`).join("\\n");
        setFormError(messages);
      } else {
        setFormError(data?.detail || "Failed to create patient.");
      }
    }
  });'''
)

# Add error banner in UI
if "{formError && (" not in p_content:
    p_content = p_content.replace(
        '<form onSubmit={onCreate} className="bg-white border rounded-lg p-6 space-y-6 shadow-sm">',
        '''<form onSubmit={onCreate} className="bg-white border rounded-lg p-6 space-y-6 shadow-sm">
          {formError && (
            <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200 text-sm whitespace-pre-wrap font-mono">
              {formError}
            </div>
          )}'''
    )

pp.write_text(p_content, encoding="utf-8")
print("   patched Patients.tsx to show API validation errors")

# ─── 5. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(ui): guarantee Staff tab; fix patient error display; fix backend pagination warnings",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")
print("\nThen, when you create a patient, if it fails, you will see the exact error in red.")