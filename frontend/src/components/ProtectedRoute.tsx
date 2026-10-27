import { Navigate, Outlet } from "react-router-dom";
import { currentUser } from "../api/auth";

export default function ProtectedRoute() {
  return currentUser() ? <Outlet /> : <Navigate to="/login" replace />;
}
