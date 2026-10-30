import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { currentUser, logout } from "../api/auth";
import {
  LayoutDashboard, Users, Calendar, FlaskConical, Scan,
  Pill, Boxes, CreditCard, BookOpen, Plug, UserCog,
  TestTube, ScanLine, BarChart, ShieldAlert, LogOut,
  ChevronLeft, ChevronRight, Menu
} from "lucide-react";

export default function Layout() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const nav = useNavigate();
  const user = currentUser();

  function handleLogout() { logout(); nav("/login"); }

  const isClinicalStaff = !user?.is_platform_admin;
  const isAdmin = user?.role === "admin" || user?.role === "finance_manager";

  // Helper component for the links
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
    if (isCollapsed) return <div className="h-4" />; // Spacer when collapsed
    return <div className="px-3 pt-6 pb-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider">{title}</div>;
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      {/* ─── SIDEBAR ─── */}
      <aside 
        className={`flex-shrink-0 bg-slate-900 flex flex-col h-full transition-all duration-300 ease-in-out ${
          isCollapsed ? "w-[72px]" : "w-64"
        }`}
      >
        {/* Logo & Toggle */}
        <div className={`h-16 flex items-center border-b border-slate-800 ${isCollapsed ? "justify-center px-0" : "justify-between px-4"}`}>
          {!isCollapsed && (
            <Link to="/dashboard" className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <span className="w-6 h-6 bg-sky-500 rounded flex items-center justify-center text-xs">N</span>
              Nimbus OPD
            </Link>
          )}
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)} 
            className="text-slate-400 hover:text-white p-1.5 rounded-md hover:bg-slate-800 transition"
          >
            {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-1 scrollbar-thin scrollbar-thumb-slate-700">
          {isClinicalStaff && (
            <>
              <SectionTitle title="Clinical" />
              <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
              <NavItem to="/patients" icon={Users} label="Patients" />
              <NavItem to="/appointments" icon={Calendar} label="Appointments" roles={["receptionist", "admin"]} />

              <SectionTitle title="Departments" />
              <NavItem to="/lab" icon={FlaskConical} label="Lab Queue" roles={["lab", "admin", "doctor"]} />
              <NavItem to="/radiology" icon={Scan} label="Radiology" roles={["radiology", "admin", "doctor"]} />
              <NavItem to="/pharmacy" icon={Pill} label="Pharmacy" roles={["pharmacist", "admin"]} />
              <NavItem to="/stock" icon={Boxes} label="Stock" roles={["pharmacist", "admin"]} />
            </>
          )}

          {isClinicalStaff && (
            <>
              <SectionTitle title="Finance" />
              <NavItem to="/billing" icon={CreditCard} label="Billing" roles={["receptionist", "admin"]} />
              <NavItem to="/accounting" icon={BookOpen} label="Accounting" roles={["accountant", "finance_manager", "admin"]} />
              <NavItem to="/integrations" icon={Plug} label="Integrations" roles={["finance_manager", "admin"]} />
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

        {/* User Profile / Footer */}
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
          <button 
            onClick={handleLogout} 
            title={isCollapsed ? "Sign out" : undefined}
            className={`bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition ${
              isCollapsed ? "p-2 flex justify-center w-full" : "w-full py-2 text-sm font-medium"
            }`}
          >
            {isCollapsed ? <LogOut size={18} /> : "Sign out"}
          </button>
        </div>
      </aside>

      {/* ─── MAIN CONTENT ─── */}
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