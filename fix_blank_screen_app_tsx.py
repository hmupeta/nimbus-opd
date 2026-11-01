#!/usr/bin/env python3
"""
fix_blank_screen_app_tsx.py
  - Fixes the missing 'Integrations' import in App.tsx that caused a blank screen.
  - Includes ALL necessary imports and routes.
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

# ─── 1. Overwrite App.tsx with ALL imports ─────────────────────────────
print("==> Overwriting App.tsx with complete imports")
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
import Payments from "./pages/Payments";
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
import Integrations from "./pages/Integrations";

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
          <Route path="/integrations" element={<Integrations />} />
          
          <Route path="/audit" element={<AuditTrail />} />
          <Route path="/reports" element={<MISReports />} />
          <Route path="/staff" element={<Staff />} />
          <Route path="/lab-catalog" element={<LabCatalog />} />
          <Route path="/radiology-catalog" element={<RadiologyCatalog />} />
          <Route path="/pharmacy-catalog" element={<PharmacyCatalog />} />
          <Route path="/platform" element={<PlatformAdminDashboard />} />
        </Route>
      </Route>
      
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
'''
write_frontend("src/App.tsx", APP)

# ─── 2. Build & Push ───────────────────────────────────────────────────
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
sh("git", "commit", "-m", "fix(frontend): add missing Integrations import to fix blank screen")
sh("git", "push", "origin", "main")

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")