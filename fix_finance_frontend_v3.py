#!/usr/bin/env python3
"""
fix_finance_frontend_v3.py -- Fixed get_page() to accept keys argument.
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

# ─── 1. The corrected page generator ───────────────────────────────────
def get_page(title, endpoint, headers, fields, keys):
    """
    title: Page heading
    endpoint: API endpoint (e.g. 'chart-of-accounts')
    headers: Table column headers
    fields: Form field definitions
    keys: The API response keys used for the table rows
    """
    # Build the form fields
    form_fields = ""
    for f in fields:
        if f.get("type") == "select":
            form_fields += (
                f'            <label className="block text-sm"><span className="text-slate-600">{f["label"]}</span>\n'
                f'              <select name="{f["name"]}" required className="mt-1 w-full border rounded-lg px-3 py-2">\n'
                f'                <option value="">Select...</option>\n'
                f'                {{options.{f["options"]}?.map((o: any) => <option key={{o.id}} value={{o.id}}>{{o.{f["label_key"]}}}</option>)}}\n'
                f'              </select>\n'
                f'            </label>\n'
            )
        else:
            form_fields += (
                f'            <label className="block text-sm"><span className="text-slate-600">{f["label"]}</span>\n'
                f'              <input type="{f["type"]}" name="{f["name"]}" required className="mt-1 w-full border rounded-lg px-3 py-2" />\n'
                f'            </label>\n'
            )

    # Build table headers
    header_jsx = "".join([f'<th className="text-left px-4 py-3">{h}</th>' for h in headers])

    # Build table rows using keys
    row_jsx = ""
    for k in keys:
        row_jsx += f'<td className="px-4 py-3">{{row.{k}}}</td>'

    # Build the options fetch based on field requirements
    needs_coa = any(f.get("options") == "coa" for f in fields if f.get("type") == "select")
    needs_sup = any(f.get("options") == "suppliers" for f in fields if f.get("type") == "select")

    if needs_coa and needs_sup:
        options_fetch = (
            '        const [coa, suppliers] = await Promise.all([\n'
            '          api.get<Paginated<any>>("/chart-of-accounts/").then(r => r.data.results),\n'
            '          api.get<Paginated<any>>("/suppliers/").then(r => r.data.results)\n'
            '        ]);\n'
            '        return { coa, suppliers };'
        )
    elif needs_coa:
        options_fetch = (
            '        const coa = await api.get<Paginated<any>>("/chart-of-accounts/").then(r => r.data.results);\n'
            '        return { coa };'
        )
    elif needs_sup:
        options_fetch = (
            '        const suppliers = await api.get<Paginated<any>>("/suppliers/").then(r => r.data.results);\n'
            '        return { suppliers };'
        )
    else:
        options_fetch = "        return {};"

    component_name = title.replace(" ", "").replace("-", "")

    content = f'''\
import {{ useState }} from "react";
import {{ useQuery, useMutation, useQueryClient }} from "@tanstack/react-query";
import {{ api }} from "../api/client";
import type {{ Paginated }} from "../api/types";

export default function {component_name}() {{
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
{form_fields}          <div className="col-span-2 flex justify-end gap-2 pt-4">
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
              <tr><td colSpan={{{len(headers)}}} className="px-4 py-8 text-center text-slate-500">No records yet.</td></tr>
            )}}
          </tbody>
        </table>
      </div>
    </div>
  );
}}
'''
    return content

# ─── 2. Generate all 5 pages ───────────────────────────────────────────
print("==> Generating Finance pages")

write_frontend("src/pages/ChartOfAccounts.tsx", get_page(
    title="Chart of Accounts",
    endpoint="chart-of-accounts",
    headers=["Code", "Name", "Type"],
    fields=[
        {"label": "Code", "name": "code", "type": "text"},
        {"label": "Name", "name": "name", "type": "text"},
        {"label": "Type (asset/liability/equity/revenue/expense)", "name": "type", "type": "text"},
    ],
    keys=["code", "name", "type"],
))

write_frontend("src/pages/Suppliers.tsx", get_page(
    title="Supplier",
    endpoint="suppliers",
    headers=["Name", "Contact", "Phone"],
    fields=[
        {"label": "Name", "name": "name", "type": "text"},
        {"label": "Contact Person", "name": "contact_name", "type": "text"},
        {"label": "Phone", "name": "phone", "type": "text"},
    ],
    keys=["name", "contact_name", "phone"],
))

write_frontend("src/pages/Expenses.tsx", get_page(
    title="Expense",
    endpoint="expenses",
    headers=["Date", "Description", "Amount", "Category"],
    fields=[
        {"label": "Date", "name": "date", "type": "date"},
        {"label": "Description", "name": "description", "type": "text"},
        {"label": "Amount (ZMW)", "name": "amount", "type": "number"},
        {"label": "Category", "name": "category", "type": "select", "options": "coa", "label_key": "name"},
    ],
    keys=["date", "description", "amount", "category_name"],
))

write_frontend("src/pages/FixedAssets.tsx", get_page(
    title="Fixed Asset",
    endpoint="fixed-assets",
    headers=["Name", "Purchase Date", "Cost", "Category"],
    fields=[
        {"label": "Name", "name": "name", "type": "text"},
        {"label": "Purchase Date", "name": "purchase_date", "type": "date"},
        {"label": "Cost (ZMW)", "name": "purchase_cost", "type": "number"},
        {"label": "Category", "name": "category", "type": "select", "options": "coa", "label_key": "name"},
    ],
    keys=["name", "purchase_date", "purchase_cost", "category_name"],
))

write_frontend("src/pages/AccountsPayable.tsx", get_page(
    title="Accounts Payable",
    endpoint="bills",
    headers=["Supplier", "Date", "Amount", "Status"],
    fields=[
        {"label": "Reference", "name": "reference", "type": "text"},
        {"label": "Date", "name": "date", "type": "date"},
        {"label": "Amount (ZMW)", "name": "amount", "type": "number"},
        {"label": "Supplier", "name": "supplier", "type": "select", "options": "suppliers", "label_key": "name"},
    ],
    keys=["supplier_name", "date", "amount", "status"],
))

# ─── 3. Verify with local Vite build ───────────────────────────────────
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
        for line in (r.stdout + r.stderr).splitlines()[-20:]:
            print(f"     {line}")
        sys.exit(1)
else:
    print("   [skip] npm not found")

# ─── 4. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT, env=os.environ)

sh("git", "add", ".")
sh("git", "commit", "-m", "fix(finance): get_page() function with correct keys parameter")
sh("git", "push", "origin", "main")

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")