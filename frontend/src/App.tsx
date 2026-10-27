import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import LandingPage from "./pages/LandingPage";
import Dashboard from "./pages/Dashboard";
import PlatformAdminDashboard from "./pages/PlatformAdminDashboard";
import Patients from "./pages/Patients";
import PatientDetail from "./pages/PatientDetail";
import VisitTimeline from "./pages/VisitTimeline";
import LabDashboard from "./pages/LabDashboard";
import PharmacyDashboard from "./pages/PharmacyDashboard";
import RadiologyDashboard from "./pages/RadiologyDashboard";
import BillingDashboard from "./pages/BillingDashboard";
import Appointments from "./pages/Appointments";
import StockDashboard from "./pages/StockDashboard";
import AuditTrail from "./pages/AuditTrail";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/platform" element={<PlatformAdminDashboard />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
          <Route path="/visits/:id" element={<VisitTimeline />} />
          <Route path="/lab" element={<LabDashboard />} />
          <Route path="/pharmacy" element={<PharmacyDashboard />} />
          <Route path="/radiology" element={<RadiologyDashboard />} />
          <Route path="/billing" element={<BillingDashboard />} />
          <Route path="/appointments" element={<Appointments />} />
          <Route path="/stock" element={<StockDashboard />} />
          <Route path="/audit" element={<AuditTrail />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
