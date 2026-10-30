#!/usr/bin/env python3
"""
add_sidebar_navigation.py
  - Replaces the top navigation with a modern, grouped sidebar.
  - Uses a fixed layout so the sidebar stays put while content scrolls.
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
LP = FRONTEND / "src" / "components" / "Layout.tsx"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT,
                          capture_output=True, text=True)

CONTENT = '''\
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { currentUser, logout } from "../api/auth";

export default function Layout() {
  const nav = useNavigate();
  const user = currentUser();

  function handleLogout() { logout(); nav("/login"); }

  const isClinicalStaff = !user?.is_platform_admin;
  const isAdmin = user?.role === "admin" || user?.role === "finance_manager";

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive 
        ? "bg-slate-800 text-white" 
        : "text-slate-300 hover:bg-slate-800/50 hover:text-white"
    }`;

  const sectionTitle = "px-3 pt-6 pb-2 text-xs font-bold text-slate-500 uppercase tracking-wider";

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      {/* ─── SIDEBAR ─── */}
      <aside className="w-64 flex-shrink-0 bg-slate-900 flex flex-col h-full">
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
          <Link to="/dashboard" className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <span className="w-6 h-6 bg-sky-500 rounded flex items-center justify-center text-xs">N</span>
            Nimbus OPD
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1 scrollbar-thin scrollbar-thumb-slate-700">
          {isClinicalStaff && (
            <>
              <div className={sectionTitle}>Clinical</div>
              <NavLink to="/dashboard" className={navLinkClass}>Dashboard</NavLink>
              <NavLink to="/patients" className={navLinkClass}>Patients</NavLink>
              {(user?.role === "receptionist" || user?.role === "admin") && (
                <NavLink to="/appointments" className={navLinkClass}>Appointments</NavLink>
              )}

              <div className={sectionTitle}>Departments</div>
              {(user?.role === "lab" || user?.role === "admin" || user?.role === "doctor") && (
                <NavLink to="/lab" className={navLinkClass}>Lab Queue</NavLink>
              )}
              {(user?.role === "radiology" || user?.role === "admin" || user?.role === "doctor") && (
                <NavLink to="/radiology" className={navLinkClass}>Radiology</NavLink>
              )}
              {(user?.role === "pharmacist" || user?.role === "admin") && (
                <NavLink to="/pharmacy" className={navLinkClass}>Pharmacy</NavLink>
              )}
              {(user?.role === "pharmacist" || user?.role === "admin") && (
                <NavLink to="/stock" className={navLinkClass}>Stock</NavLink>
              )}
            </>
          )}

          {isClinicalStaff && (
            <>
              <div className={sectionTitle}>Finance</div>
              {(user?.role === "receptionist" || user?.role === "admin") && (
                <NavLink to="/billing" className={navLinkClass}>Billing</NavLink>
              )}
              {(user?.role === "accountant" || user?.role === "finance_manager" || user?.role === "admin") && (
                <>
                  <NavLink to="/accounting" className={navLinkClass}>Accounting</NavLink>
                  <NavLink to="/integrations" className={navLinkClass}>Integrations</NavLink>
                </>
              )}
            </>
          )}

          {isClinicalStaff && isAdmin && (
            <>
              <div className={sectionTitle}>Administration</div>
              <NavLink to="/staff" className={navLinkClass}>Staff</NavLink>
              <NavLink to="/lab-catalog" className={navLinkClass}>Lab Catalog</NavLink>
              <NavLink to="/radiology-catalog" className={navLinkClass}>Radiology Catalog</NavLink>
              <NavLink to="/pharmacy-catalog" className={navLinkClass}>Pharmacy Catalog</NavLink>
              <NavLink to="/reports" className={navLinkClass}>MIS Reports</NavLink>
              <NavLink to="/audit" className={navLinkClass}>Audit Trail</NavLink>
            </>
          )}

          {user?.is_platform_admin && (
            <>
              <div className={sectionTitle}>Platform</div>
              <NavLink to="/platform" className={navLinkClass}>Platform Admin</NavLink>
            </>
          )}
        </nav>

        {/* User Profile / Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-sky-400 font-bold">
              {user?.full_name?.charAt(0) || user?.email?.charAt(0) || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.full_name || "User"}</p>
              <p className="text-xs text-slate-400 capitalize truncate">{user?.role}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-medium rounded transition">
            Sign out
          </button>
        </div>
      </aside>

      {/* ─── MAIN CONTENT ─── */}
      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Top header for mobile/tablet (optional, keeping it clean for now) */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center px-6 lg:hidden">
          <span className="font-bold text-slate-800">Nimbus OPD</span>
        </header>

        {/* Scrollable page content */}
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

# ─── 1. Write the new Layout ───────────────────────────────────────────
print("==> Overwriting Layout.tsx with Sidebar navigation")
LP.write_text(CONTENT.strip(), encoding="utf-8")
print(f"   wrote {LP.name}")

# ─── 2. Verify with local Vite build ───────────────────────────────────
print("\n==> Running local Vite build to verify")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    import os
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Local Vite build succeeded!")
    else:
        print("   ❌ Local Vite build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print(f"     {line}")
        sys.exit(1)

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "feat(ui): replace top nav with grouped sidebar menu", check=False)
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")