import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { currentUser, logout } from "../api/auth";

export default function Layout() {
  const nav = useNavigate();
  const user = currentUser();

  function handleLogout() { logout(); nav("/login"); }

  const isClinicalStaff = !user?.is_platform_admin;

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium ${
      isActive ? "bg-sky-100 text-sky-700" : "text-slate-600 hover:bg-slate-100"
    }`;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200 no-print">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6">
          <Link to="/dashboard" className="text-lg font-bold text-sky-700">OPD</Link>
          <nav className="flex gap-2">
            {isClinicalStaff && <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>}
            {isClinicalStaff && <NavLink to="/patients" className={linkClass}>Patients</NavLink>}
            
            {isClinicalStaff && (user?.role === "receptionist" || user?.role === "admin") ? (
              <NavLink to="/appointments" className={linkClass}>Appointments</NavLink>
            ) : null}

            {isClinicalStaff && (user?.role === "lab" || user?.role === "admin") ? (
              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>
            ) : null}

            {isClinicalStaff && (user?.role === "radiology" || user?.role === "admin") ? (
              <NavLink to="/radiology" className={linkClass}>Radiology</NavLink>
            ) : null}

            {isClinicalStaff && (user?.role === "pharmacist" || user?.role === "admin") ? (
              <NavLink to="/pharmacy" className={linkClass}>Pharmacy</NavLink>
            ) : null}

            {isClinicalStaff && (user?.role === "pharmacist" || user?.role === "admin") ? (
              <NavLink to="/stock" className={linkClass}>Stock</NavLink>
            ) : null}

            {isClinicalStaff && (user?.role === "receptionist" || user?.role === "admin") ? (
              <NavLink to="/billing" className={linkClass}>Billing</NavLink>
            ) : null}

            {!user?.is_platform_admin && user?.role === "admin" && (
              <NavLink to="/audit" className={linkClass}>Audit Trail</NavLink>
            )}

            {user?.is_platform_admin && (
              <NavLink to="/platform" className={linkClass}>Platform Admin</NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-slate-600">
            {user ? (
              <>
                <span>{user.full_name || user.email}</span>
                <span className="text-xs bg-slate-100 px-2 py-0.5 rounded">{user.role}</span>
                <button
                  onClick={handleLogout}
                  className="px-3 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200"
                >
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
