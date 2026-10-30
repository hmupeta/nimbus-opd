#!/usr/bin/env python3
"""
add_finance_frontend.py
  - Creates the frontend pages for COA, Suppliers, Expenses, AP, Fixed Assets.
  - Updates the sidebar and router.
  - Builds and pushes.
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
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. Generate the 5 finance pages ───────────────────────────────────
def generate_page(title, endpoint, columns, form_fields, extra_opts=None):
    # Build the form fields
    input_fields = ""
    select_fields = ""
    for f in form_fields:
        if f['type'] == 'select':
            select_fields += f'''
            <label className="block text-sm"><span className="text-slate-600">{f['label']}</span>
              <select name="{f['name']}" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="">Select...</option>
                {{options.{f['options_key']}?.map((o: any) => <option key={{o.id}} value={{o.id}}>{{o.{f['option_label']}}}</option>)}}
              </select>
            </label>'''
        else:
            input_fields += f'''
            <label className="block text-sm"><span className="text-slate-600">{f['label']}</span>
              <input type="{f['type']}" name="{f['name']}" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>'''

    header_html = "".join([f'<th className="text-left px-4 py-3">{c["label"]}</th>' for c in columns])
    row_html = "".join([f'<td className="px-4 py-3">{{{{row.{c["key"]}}}}}</td>' for c in columns])

    # Options query (only fetch what's needed)
    needs_coa = any(f.get('options_key') == 'coa' for f in form_fields if f['type'] == 'select')
    needs_sup = any(f.get('options_key') == 'suppliers' for f in form_fields if f['type'] == 'select')

    options_query = ""
    if needs_coa or needs_sup:
        calls = []
        if needs_coa:
            calls.append('api.get<Paginated<any>>("/chart-of-accounts/").then(r => r.data.results)')
        if needs_sup:
            calls.append('api.get<Paginated<any>>("/suppliers/").then(r => r.data.results)')
        
        destructure = []
        if needs_coa: destructure.append("coa")
        if needs_sup: destructure.append("suppliers")
        destr_str = ", ".join(destructure)
        
        options_query = f'''
  const options = useQuery({{
    queryKey: ["finance-options-{endpoint}"],
    queryFn: async () => {{
      const [{destr_str}] = await Promise.all([{", ".join(calls)}]);
      return {{ {destr_str} }};
    }}
  }});'''
    else:
        options_query = '''
  const options: any = { data: {} };'''

    content = f'''\
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
  }});{options_query}

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
          {input_fields}
          {select_fields}
          <div className="col-span-2 flex justify-end gap-2 pt-4">
            <button type="button" onClick={{() => setShowForm(false)}} className="px-4 py-2 border rounded-lg text-slate-600">Cancel</button>
            <button type="submit" disabled={{createItem.isPending}} className="px-4 py-2 bg-sky-600 text-white rounded-lg">Save</button>
          </div>
        </form>
      )}}

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr>{header_html}</tr></thead>
          <tbody className="divide-y">
            {{data.data?.map((row: any) => (
              <tr key={{row.id}} className="hover:bg-slate-50">{row_html}</tr>
            ))}}
            {{data.data?.length === 0 && (
              <tr><td colSpan={{{len(columns)}}} className="px-4 py-8 text-center text-slate-500">No {title.lower()} yet.</td></tr>
            )}}
          </tbody>
        </table>
      </div>
    </div>
  );
}}
'''
    return content

# 1. Chart of Accounts
write_frontend("src/pages/ChartOfAccounts.tsx", generate_page(
    title="Chart of Accounts",
    endpoint="chart-of-accounts",
    columns=[{"label":"Code","key":"code"},{"label":"Name","key":"name"},{"label":"Type","key":"type"}],
    form_fields=[
        {"label":"Code","name":"code","type":"text"},
        {"label":"Name","name":"name","type":"text"},
        {"label":"Type","name":"type","type":"select","options_key":"types","option_label":"label"},
    ]
))

# 2. Suppliers
write_frontend("src/pages/Suppliers.tsx", generate_page(
    title="Supplier",
    endpoint="suppliers",
    columns=[{"label":"Name","key":"name"},{"label":"Contact","key":"contact_name"},{"label":"Phone","key":"phone"}],
    form_fields=[
        {"label":"Name","name":"name","type":"text"},
        {"label":"Contact Person","name":"contact_name","type":"text"},
        {"label":"Phone","name":"phone","type":"text"},
    ]
))

# 3. Expenses
write_frontend("src/pages/Expenses.tsx", generate_page(
    title="Expense",
    endpoint="expenses",
    columns=[{"label":"Date","key":"date"},{"label":"Description","key":"description"},{"label":"Amount","key":"amount"},{"label":"Category","key":"category_name"}],
    form_fields=[
        {"label":"Date","name":"date","type":"date"},
        {"label":"Description","name":"description","type":"text"},
        {"label":"Amount (ZMW)","name":"amount","type":"number"},
        {"label":"Category","name":"category","type":"select","options_key":"coa","option_label":"name"},
    ]
))

# 4. Fixed Assets
write_frontend("src/pages/FixedAssets.tsx", generate_page(
    title="Fixed Asset",
    endpoint="fixed-assets",
    columns=[{"label":"Name","key":"name"},{"label":"Purchase Date","key":"purchase_date"},{"label":"Cost","key":"purchase_cost"},{"label":"Category","key":"category_name"}],
    form_fields=[
        {"label":"Name","name":"name","type":"text"},
        {"label":"Purchase Date","name":"purchase_date","type":"date"},
        {"label":"Purchase Cost (ZMW)","name":"purchase_cost","type":"number"},
        {"label":"Category","name":"category","type":"select","options_key":"coa","option_label":"name"},
    ]
))

# 5. Accounts Payable (Bills)
write_frontend("src/pages/AccountsPayable.tsx", generate_page(
    title="Accounts Payable",
    endpoint="bills",
    columns=[{"label":"Supplier","key":"supplier_name"},{"label":"Date","key":"date"},{"label":"Amount","key":"amount"},{"label":"Status","key":"status"}],
    form_fields=[
        {"label":"Reference","name":"reference","type":"text"},
        {"label":"Date","name":"date","type":"date"},
        {"label":"Amount (ZMW)","name":"amount","type":"number"},
        {"label":"Supplier","name":"supplier","type":"select","options_key":"suppliers","option_label":"name"},
    ]
))

# ─── 2. Patch Layout.tsx to add finance links ──────────────────────────
print("\n==> Patching Layout.tsx (sidebar)")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")

old_finance = '''              <NavLink to="/accounting" icon={BookOpen} label="Accounting" roles={["accountant", "finance_manager", "admin"]} />
              <NavLink to="/integrations" icon={Plug} label="Integrations" roles={["finance_manager", "admin"]} />'''

new_finance = '''              <NavLink to="/accounting" icon={BookOpen} label="General Ledger" roles={["accountant", "finance_manager", "admin"]} />
              <NavLink to="/chart-of-accounts" icon={BookOpen} label="Chart of Accounts" roles={["accountant", "finance_manager", "admin"]} />
              <NavLink to="/expenses" icon={CreditCard} label="Expenses" roles={["accountant", "finance_manager", "admin"]} />
              <NavLink to="/accounts-payable" icon={CreditCard} label="Accounts Payable" roles={["accountant", "finance_manager", "admin"]} />
              <NavLink to="/fixed-assets" icon={Boxes} label="Fixed Assets" roles={["accountant", "finance_manager", "admin"]} />
              <NavLink to="/suppliers" icon={UserCog} label="Suppliers" roles={["accountant", "finance_manager", "admin"]} />
              <NavLink to="/integrations" icon={Plug} label="Integrations" roles={["finance_manager", "admin"]} />'''

if old_finance in l:
    l = l.replace(old_finance, new_finance)
    lp.write_text(l, encoding="utf-8")
    print("   added finance module links to sidebar")
else:
    print("   [WARN] Could not find the exact Finance block in Layout.tsx")

# ─── 3. Patch App.tsx to add finance routes ────────────────────────────
print("\n==> Patching App.tsx (router)")
ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")

imports = '''import ChartOfAccounts from "./pages/ChartOfAccounts";
import Suppliers from "./pages/Suppliers";
import Expenses from "./pages/Expenses";
import FixedAssets from "./pages/FixedAssets";
import AccountsPayable from "./pages/AccountsPayable";
'''

routes = '''          <Route path="/chart-of-accounts" element={<ChartOfAccounts />} />
          <Route path="/suppliers" element={<Suppliers />} />
          <Route path="/expenses" element={<Expenses />} />
          <Route path="/fixed-assets" element={<FixedAssets />} />
          <Route path="/accounts-payable" element={<AccountsPayable />} />
'''

if "ChartOfAccounts" not in a:
    # Insert imports after the accounting dashboard import
    if 'import AccountingDashboard from "./pages/AccountingDashboard";' in a:
        a = a.replace(
            'import AccountingDashboard from "./pages/AccountingDashboard";',
            'import AccountingDashboard from "./pages/AccountingDashboard";\n' + imports
        )
    else:
        # Fallback: after the last import
        a = a.replace(
            'import "./index.css";',
            'import "./index.css";\n' + imports
        )

    # Insert routes after the accounting route
    if '<Route path="/accounting" element={<AccountingDashboard />} />' in a:
        a = a.replace(
            '<Route path="/accounting" element={<AccountingDashboard />} />',
            '<Route path="/accounting" element={<AccountingDashboard />} />\n' + routes
        )
    else:
        print("   [WARN] Could not find the /accounting route")

    ap.write_text(a, encoding="utf-8")
    print("   added finance routes to App.tsx")

# ─── 4. Local build check ──────────────────────────────────────────────
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

# ─── 5. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT, env=os.environ)

sh("git", "add", ".")
sh("git", "commit", "-m", "feat(finance): add frontend UI for COA, Suppliers, Expenses, AP, Fixed Assets")
sh("git", "push", "origin", "main")

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")