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
import AccountingDashboard from "./pages/AccountingDashboard";
import ChartOfAccounts from "./pages/ChartOfAccounts";
import Suppliers from "./pages/Suppliers";
import Expenses from "./pages/Expenses";
import FixedAssets from "./pages/FixedAssets";
import AccountsPayable from "./pages/AccountsPayable";

import Integrations from "./pages/Integrations";
import MISReports from "./pages/MISReports";
import Staff from "./pages/Staff";
import LabCatalog from "./pages/LabCatalog";
import RadiologyCatalog from "./pages/RadiologyCatalog";
import PharmacyCatalog from "./pages/PharmacyCatalog";
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
          <Route path="/accounting" element={<AccountingDashboard />} />
          <Route path="/chart-of-accounts" element={<ChartOfAccounts />} />
          <Route path="/suppliers" element={<Suppliers />} />
          <Route path="/expenses" element={<Expenses />} />
          <Route path="/fixed-assets" element={<FixedAssets />} />
          <Route path="/accounts-payable" element={<AccountsPayable />} />

          <Route path="/integrations" element={<Integrations />} />
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
