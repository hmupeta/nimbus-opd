#!/usr/bin/env python3
"""
fix_finance_frontend_v2.py
  - Overwrites Layout.tsx to include finance links safely.
  - Overwrites the 5 finance pages with clean, literal JSX.
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
              <NavItem to="/accounting" icon={BookOpen} label="General Ledger" roles={["accountant", "finance_manager", "admin"]} />
              <NavItem to="/chart-of-accounts" icon={Landmark} label="Chart of Accounts" roles={["accountant", "finance_manager", "admin"]} />
              <NavItem to="/expenses" icon={Receipt} label="Expenses" roles={["accountant", "finance_manager", "admin"]} />
              <NavItem to="/accounts-payable" icon={CreditCard} label="Accounts Payable" roles={["accountant", "finance_manager", "admin"]} />
              <NavItem to="/fixed-assets" icon={Boxes} label="Fixed Assets" roles={["accountant", "finance_manager", "admin"]} />
              <NavItem to="/suppliers" icon={Building2} label="Suppliers" roles={["accountant", "finance_manager", "admin"]} />
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

# ─── 2. Overwrite the 5 Finance Pages ──────────────────────────────────
print("==> Overwriting Finance pages with clean JSX")

# A helper to reduce boilerplate
def get_page(title, endpoint, headers, fields):
    header_jsx = "".join([f'<th className="text-left px-4 py-3">{h}</th>' for h in headers])
    
    form_fields = ""
    for f in fields:
        if f.get("type") == "select":
            form_fields += f'''
            <label className="block text-sm"><span className="text-slate-600">{f["label"]}</span>
              <select name="{f["name"]}" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="">Select...</option>
                {{options.{f["options"]}?.map((o: any) => <option key={{o.id}} value={{o.id}}>{{o.{f["label_key"]}}}</option>)}}
              </select>
            </label>'''
        else:
            form_fields += f'''
            <label className="block text-sm"><span className="text-slate-600">{f["label"]}</span>
              <input type="{f["type"]}" name="{f["name"]}" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>'''

    row_jsx = ""
    for k in f.get("keys", []):
        row_jsx += f'<td className="px-4 py-3">{{row.{k}}}</td>'
    
    # Build options query if needed
    needs_coa = any(f.get("options") == "coa" for f in fields if f.get("type") == "select")
    needs_sup = any(f.get("options") == "suppliers" for f in fields if f.get("type") == "select")
    
    options_fetch = ""
    if needs_coa and needs_sup:
        options_fetch = '''
      const [coa, suppliers] = await Promise.all([
        api.get<Paginated<any>>("/chart-of-accounts/").then(r => r.data.results),
        api.get<Paginated<any>>("/suppliers/").then(r => r.data.results)
      ]);
      return { coa, suppliers };'''
    elif needs_coa:
        options_fetch = '''
      const coa = await api.get<Paginated<any>>("/chart-of-accounts/").then(r => r.data.results);
      return { coa };'''
    elif needs_sup:
        options_fetch = '''
      const suppliers = await api.get<Paginated<any>>("/suppliers/").then(r => r.data.results);
      return { suppliers };'''
    else:
        options_fetch = "return {};"

    return f'''\
import {{ useState }} from "react";
import {{ useQuery, useMutation, useQueryClient }} from "@tanstack/react-query";
import {{ api }} from "../api/client";
import type {{ Paginated }} from "../api/types";

export default function {title.replace(" ", "")}() {{
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const data = useQuery({{
    queryKey: ["{endpoint}"],
    queryFn: async () => (await api.get<Paginated<any>>("/{endpoint}/")).data.results,
  }});

  const options = useQuery({{
    queryKey: ["finance-options-{endpoint}"],
    queryFn: async () => {{
      {options_fetch}
    }}
  }});

  const createItem = useMutation({{
    mutationFn: async (payload: any) => await api.post("/{endpoint}/", payload),
    onSuccess: () => {{ qc.invalidateQueries({{ queryKey: ["{endpoint}"] }}); setShowForm(false); }},
  }});

  function onSubmit(e: any) {{
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: any = {{}};
    fd.forEach((v, k) => payload[k] = v);
    createItem.mutate(payload);
  }}

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-800">{title}</h1>
        <button onClick={{() => setShowForm(!showForm)}} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium">
          + New {title}
        </button>
      </div>

      {{showForm && (
        <form onSubmit={{onSubmit}} className="bg-white border rounded-xl p-6 shadow-sm grid grid-cols-2 gap-4">
          {form_fields}
          <div className="col-span-2 flex justify-end gap-2 pt-4">
            <button type="button" onClick={{() => setShowForm(false)}} className="px-4 py-2 border rounded-lg text-slate-600">Cancel</button>
            <button type="submit" disabled={{createItem.isPending}} className="px-4 py-2 bg-sky-600 text-white rounded-lg">Save</button>
          </div>
        </form>
      )}}

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr>{header_jsx}</tr></thead>
          <tbody className="divide-y">
            {{data.data?.map((row: any) => (
              <tr key={{row.id}} className="hover:bg-slate-50">
                {row_jsx}
              </tr>
            ))}}
            {{data.data?.length === 0 && (
              <tr><td colSpan={{{len(headers)}}} className="px-4 py-8 text-center text-slate-500">No {title.lower()} yet.</td></tr>
            )}}
          </tbody>
        </table>
      </div>
    </div>
  );
}}
'''

write_frontend("src/pages/ChartOfAccounts.tsx", get_page(
    title="Chart of Accounts", endpoint="chart-of-accounts",
    headers=["Code", "Name", "Type"],
    fields=[
        {"label":"Code","name":"code","type":"text"},
        {"label":"Name","name":"name","type":"text"},
        {"label":"Type","name":"type","type":"text"}, # simple text for now
    ],
    keys=["code", "name", "type"]
))

write_frontend("src/pages/Suppliers.tsx", get_page(
    title="Supplier", endpoint="suppliers",
    headers=["Name", "Contact", "Phone"],
    fields=[
        {"label":"Name","name":"name","type":"text"},
        {"label":"Contact Person","name":"contact_name","type":"text"},
        {"label":"Phone","name":"phone","type":"text"},
    ],
    keys=["name", "contact_name", "phone"]
))

write_frontend("src/pages/Expenses.tsx", get_page(
    title="Expense", endpoint="expenses",
    headers=["Date", "Description", "Amount", "Category"],
    fields=[
        {"label":"Date","name":"date","type":"date"},
        {"label":"Description","name":"description","type":"text"},
        {"label":"Amount (ZMW)","name":"amount","type":"number"},
        {"label":"Category","name":"category","type":"select","options":"coa","label_key":"name"},
    ],
    keys=["date", "description", "amount", "category_name"]
))

write_frontend("src/pages/FixedAssets.tsx", get_page(
    title="Fixed Asset", endpoint="fixed-assets",
    headers=["Name", "Purchase Date", "Cost", "Category"],
    fields=[
        {"label":"Name","name":"name","type":"text"},
        {"label":"Purchase Date","name":"purchase_date","type":"date"},
        {"label":"Cost (ZMW)","name":"purchase_cost","type":"number"},
        {"label":"Category","name":"category","type":"select","options":"coa","label_key":"name"},
    ],
    keys=["name", "purchase_date", "purchase_cost", "category_name"]
))

write_frontend("src/pages/AccountsPayable.tsx", get_page(
    title="Accounts Payable", endpoint="bills",
    headers=["Supplier", "Date", "Amount", "Status"],
    fields=[
        {"label":"Reference","name":"reference","type":"text"},
        {"label":"Date","name":"date","type":"date"},
        {"label":"Amount (ZMW)","name":"amount","type":"number"},
        {"label":"Supplier","name":"supplier","type":"select","options":"suppliers","label_key":"name"},
    ],
    keys=["supplier_name", "date", "amount", "status"]
))

# ─── 3. Local build check ──────────────────────────────────────────────
print("\n==> Running local Vite build to verify")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
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

# ─── 4. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT, env=os.environ)

sh("git", "add", ".")
sh("git", "commit", "-m", "fix(finance): overwrite UI pages with clean JSX and fix sidebar links")
sh("git", "push", "origin", "main")

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")