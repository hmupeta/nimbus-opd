#!/usr/bin/env python3
"""
force_financial_reports_ui.py
  - Force overwrites Layout.tsx and App.tsx to guarantee the Financial Reports page is wired up.
"""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. Overwrite Layout.tsx ───────────────────────────────────────────
print("==> Overwriting Layout.tsx")
LAYOUT = '''\
import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { currentUser, logout } from "../api/auth";
import {
  LayoutDashboard, Users, Calendar, FlaskConical, Scan,
  Pill, Boxes, CreditCard, BookOpen, Plug, UserCog,
  TestTube, ScanLine, BarChart, ShieldAlert, LogOut,
  ChevronLeft, ChevronRight, Menu, Landmark, Receipt, Building2
} from "lucide-react";

export default function Layout() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const nav = useNavigate();
  const user = currentUser();

  function handleLogout() { logout(); nav("/login"); }

  const isClinicalStaff = !user?.is_platform_admin;
  const isAdmin = user?.role === "admin" || user?.role === "finance_manager";

  const NavItem = ({ to, icon: Icon, label, roles }: { to: string, icon: any, label: string, roles?: string[] }) => {
    if (roles && !roles.includes(user?.role || "")) return null;
    return (
      <NavLink 
        to={to} 
        title={isCollapsed ? label : undefined}
        className={({ isActive }) =>
          `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
            isActive 
              ? "bg-sky-600 text-white shadow-md" 
              : "text-slate-300 hover:bg-slate-800 hover:text-white"
          } ${isCollapsed ? "justify-center" : ""}`
        }
      >
        <Icon size={18} className="shrink-0" />
        {!isCollapsed && <span className="truncate">{label}</span>}
      </NavLink>
    );
  };

  const SectionTitle = ({ title }: { title: string }) => {
    if (isCollapsed) return <div className="h-4" />;
    return <div className="px-3 pt-6 pb-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider">{title}</div>;
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      <aside className={`flex-shrink-0 bg-slate-900 flex flex-col h-full transition-all duration-300 ease-in-out ${isCollapsed ? "w-[72px]" : "w-64"}`}>
        <div className={`h-16 flex items-center border-b border-slate-800 ${isCollapsed ? "justify-center px-0" : "justify-between px-4"}`}>
          {!isCollapsed && (
            <Link to="/dashboard" className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <span className="w-6 h-6 bg-sky-500 rounded flex items-center justify-center text-xs">N</span>
              Nimbus OPD
            </Link>
          )}
          <button onClick={() => setIsCollapsed(!isCollapsed)} className="text-slate-400 hover:text-white p-1.5 rounded-md hover:bg-slate-800 transition">
            {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-1 scrollbar-thin scrollbar-thumb-slate-700">
          {isClinicalStaff && (
            <>
              <SectionTitle title="Clinical" />
              <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
              <NavItem to="/patients" icon={Users} label="Patients" />
              <NavItem to="/appointments" icon={Calendar} label="Appointments" roles={["receptionist", "admin"]} />

              <SectionTitle title="Departments" />
              <NavItem to="/lab" icon={FlaskConical} label="Lab Queue" roles={["lab", "admin"]} />
              <NavItem to="/radiology" icon={Scan} label="Radiology" roles={["radiology", "admin"]} />
              <NavItem to="/pharmacy" icon={Pill} label="Pharmacy" roles={["pharmacist", "admin"]} />
              <NavItem to="/stock" icon={Boxes} label="Stock" roles={["pharmacist", "admin"]} />
            </>
          )}

          {isClinicalStaff && (
            <>
              <SectionTitle title="Finance" />
              <NavItem to="/billing" icon={CreditCard} label="Billing" roles={["receptionist", "admin"]} />
              <NavItem to="/payments" icon={Receipt} label="Payments" roles={["receptionist", "admin", "accountant", "finance_manager"]} />
              
              {(user?.role === "accountant" || user?.role === "finance_manager" || user?.role === "admin") && (
                <>
                  <NavItem to="/accounting" icon={BookOpen} label="General Ledger" roles={["accountant", "finance_manager", "admin"]} />
                  <NavItem to="/financial-reports" icon={BarChart} label="Financial Reports" roles={["accountant", "finance_manager", "admin"]} />
                  <NavItem to="/chart-of-accounts" icon={Landmark} label="Chart of Accounts" roles={["accountant", "finance_manager", "admin"]} />
                  <NavItem to="/expenses" icon={Receipt} label="Expenses" roles={["accountant", "finance_manager", "admin"]} />
                  <NavItem to="/accounts-payable" icon={CreditCard} label="Accounts Payable" roles={["accountant", "finance_manager", "admin"]} />
                  <NavItem to="/fixed-assets" icon={Boxes} label="Fixed Assets" roles={["accountant", "finance_manager", "admin"]} />
                  <NavItem to="/suppliers" icon={Building2} label="Suppliers" roles={["accountant", "finance_manager", "admin"]} />
                  <NavItem to="/integrations" icon={Plug} label="Integrations" roles={["finance_manager", "admin"]} />
                </>
              )}
            </>
          )}

          {isClinicalStaff && isAdmin && (
            <>
              <SectionTitle title="Administration" />
              <NavItem to="/staff" icon={UserCog} label="Staff" roles={["admin"]} />
              <NavItem to="/lab-catalog" icon={TestTube} label="Lab Catalog" roles={["admin"]} />
              <NavItem to="/radiology-catalog" icon={ScanLine} label="Radiology Catalog" roles={["admin"]} />
              <NavItem to="/pharmacy-catalog" icon={Pill} label="Pharmacy Catalog" roles={["admin"]} />
              <NavItem to="/reports" icon={BarChart} label="MIS Reports" roles={["admin"]} />
              <NavItem to="/audit" icon={ShieldAlert} label="Audit Trail" roles={["admin"]} />
            </>
          )}

          {user?.is_platform_admin && (
            <>
              <SectionTitle title="Platform" />
              <NavItem to="/platform" icon={Menu} label="Platform Admin" />
            </>
          )}
        </nav>

        <div className={`p-3 border-t border-slate-800 bg-slate-900 ${isCollapsed ? "flex flex-col items-center" : ""}`}>
          <div className={`flex items-center gap-3 mb-3 ${isCollapsed ? "justify-center w-full" : ""}`}>
            <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center text-sky-400 font-bold shrink-0">
              {user?.full_name?.charAt(0) || user?.email?.charAt(0) || "U"}
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{user?.full_name || "User"}</p>
                <p className="text-xs text-slate-400 capitalize truncate">{user?.role}</p>
              </div>
            )}
          </div>
          <button onClick={handleLogout} title={isCollapsed ? "Sign out" : undefined} className={`bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition ${isCollapsed ? "p-2 flex justify-center w-full" : "w-full py-2 text-sm font-medium"}`}>
            {isCollapsed ? <LogOut size={18} /> : "Sign out"}
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div className="max-w-6xl mx-auto h-full">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
'''
write_frontend("src/components/Layout.tsx", LAYOUT)

# ─── 2. Overwrite App.tsx Router ───────────────────────────────────────
print("==> Overwriting App.tsx")
APP = '''\
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
import LabCatalog from "./pages/LabCatalog";
import RadiologyCatalog from "./pages/RadiologyCatalog";
import PharmacyCatalog from "./pages/PharmacyCatalog";
import PlatformAdminDashboard from "./pages/PlatformAdminDashboard";
import AccountingDashboard from "./pages/AccountingDashboard";
import FinancialReports from "./pages/FinancialReports";
import ChartOfAccounts from "./pages/ChartOfAccounts";
import Suppliers from "./pages/Suppliers";
import Expenses from "./pages/Expenses";
import FixedAssets from "./pages/FixedAssets";
import AccountsPayable from "./pages/AccountsPayable";
import Payments from "./pages/Payments";

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
          <Route path="/payments" element={<Payments />} />
          
          <Route path="/accounting" element={<AccountingDashboard />} />
          <Route path="/financial-reports" element={<FinancialReports />} />
          <Route path="/chart-of-accounts" element={<ChartOfAccounts />} />
          <Route path="/suppliers" element={<Suppliers />} />
          <Route path="/expenses" element={<Expenses />} />
          <Route path="/fixed-assets" element={<FixedAssets />} />
          <Route path="/accounts-payable" element={<AccountsPayable />} />
          
          <Route path="/audit" element={<AuditTrail />} />
          <Route path="/reports" element={<MISReports />} />
          <Route path="/staff" element={<Staff />} />
          <Route path="/lab-catalog" element={<LabCatalog />} />
          <Route path="/radiology-catalog" element={<RadiologyCatalog />} />
          <Route path="/pharmacy-catalog" element={<PharmacyCatalog />} />
          <Route path="/integrations" element={<Integrations />} />
          <Route path="/platform" element={<PlatformAdminDashboard />} />
        </Route>
      </Route>
      
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
'''
write_frontend("src/App.tsx", APP)

# ─── 3. Build & Push ───────────────────────────────────────────────────
print("\n==> Running local Vite build to verify")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    env = __import__("os").environ.copy()
    env["PATH"] = str(Path(npm).parent) + __import__("os").pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Local Vite build succeeded!")
    else:
        print("   ❌ Local Vite build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print(f"     {line}")
        sys.exit(1)

print("\n==> Committing and pushing")
def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)

sh("git", "add", ".")
sh("git", "commit", "-m", "fix(frontend): force overwrite App.tsx and Layout.tsx to expose Financial Reports")
sh("git", "push", "origin", "main")

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")