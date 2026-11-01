#!/usr/bin/env python3
"""
add_payments_page.py
  - Updates the backend PaymentSerializer to include patient & visit info.
  - Creates a new Payments page in the frontend.
  - Adds the link to the sidebar and router.
"""
from __future__ import annotations
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Update PaymentSerializer ──────────────────────────────
print("==> Patching api/billing_serializers.py")
bsp = ROOT / "api" / "billing_serializers.py"
bs = bsp.read_text(encoding="utf-8")

old_serializer = '''class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "invoice", "amount", "method", "reference",
                  "mobile_money_config", "payment_gateway_config",
                  "paid_at", "received_by", "notes"]
        read_only_fields = ["id", "received_by"]'''

new_serializer = '''class PaymentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="invoice.patient.full_name", read_only=True)
    visit_no = serializers.CharField(source="invoice.visit.visit_no", read_only=True)
    received_by_name = serializers.CharField(source="received_by.full_name", read_only=True, default="System")

    class Meta:
        model = Payment
        fields = ["id", "invoice", "patient_name", "visit_no", "amount", "method", "reference",
                  "mobile_money_config", "payment_gateway_config",
                  "paid_at", "received_by", "received_by_name", "notes"]
        read_only_fields = ["id", "received_by"]'''

if old_serializer in bs:
    bs = bs.replace(old_serializer, new_serializer)
    bsp.write_text(bs, encoding="utf-8")
    print("   patched PaymentSerializer")
else:
    print("   [WARN] Could not find exact PaymentSerializer to patch. Trying regex...")
    bs = re.sub(
        r"class PaymentSerializer\(serializers\.ModelSerializer\):.*?(?=\nclass |\Z)",
        new_serializer + "\n",
        bs,
        count=1,
        flags=re.DOTALL
    )
    bsp.write_text(bs, encoding="utf-8")

# ─── 2. FRONTEND: Create Payments.tsx ──────────────────────────────────
print("==> Creating src/pages/Payments.tsx")
CONTENT = '''\
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function Payments() {
  const payments = useQuery({
    queryKey: ["payments"],
    queryFn: async () => (await api.get<Paginated<any>>("/payments/")).data.results,
  });

  const getMethodColor = (method: string) => {
    switch (method) {
      case "cash": return "bg-emerald-100 text-emerald-700";
      case "mobile_money": return "bg-amber-100 text-amber-700";
      case "card": return "bg-indigo-100 text-indigo-700";
      case "insurance": return "bg-sky-100 text-sky-700";
      default: return "bg-slate-100 text-slate-700";
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Payments History</h1>
        <p className="text-sm text-slate-500 mt-1">A complete ledger of all payments received.</p>
      </div>

      {payments.isLoading && <p className="text-slate-500">Loading...</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3">Date & Time</th>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Visit No</th>
              <th className="text-left px-4 py-3">Amount</th>
              <th className="text-left px-4 py-3">Method</th>
              <th className="text-left px-4 py-3">Reference</th>
              <th className="text-left px-4 py-3">Received By</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {payments.data?.map((p: any) => (
              <tr key={p.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                  {new Date(p.paid_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}
                </td>
                <td className="px-4 py-3 font-medium text-slate-800">{p.patient_name}</td>
                <td className="px-4 py-3 font-mono text-xs">{p.visit_no}</td>
                <td className="px-4 py-3 font-bold text-slate-800">ZMW {p.amount}</td>
                <td className="px-4 py-3">
                  <span className={`text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wide ${getMethodColor(p.method)}`}>
                    {p.method.replace("_", " ")}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{p.reference || "—"}</td>
                <td className="px-4 py-3 text-slate-600">{p.received_by_name}</td>
              </tr>
            ))}
            {payments.data?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No payments recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
'''
write_frontend("src/pages/Payments.tsx", CONTENT)

# ─── 3. FRONTEND: Update Layout & Router ───────────────────────────────
print("==> Updating Layout.tsx (Sidebar)")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")

# Add Payments link under Finance
if "Payments" not in l:
    l = l.replace(
        '<NavLink to="/billing" icon={CreditCard} label="Billing" roles={["receptionist", "admin"]} />',
        '<NavLink to="/billing" icon={CreditCard} label="Billing" roles={["receptionist", "admin"]} />\n'
        '              <NavLink to="/payments" icon={CreditCard} label="Payments" roles={["admin", "finance_manager", "accountant", "receptionist"]} />'
    )
    lp.write_text(l, encoding="utf-8")
    print("   added Payments link to sidebar")

print("==> Updating App.tsx (Router)")
ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")

if "Payments" not in a:
    a = a.replace(
        'import BillingDashboard from "./pages/BillingDashboard";',
        'import BillingDashboard from "./pages/BillingDashboard";\nimport Payments from "./pages/Payments";'
    )
    a = a.replace(
        '<Route path="/billing" element={<BillingDashboard />} />',
        '<Route path="/billing" element={<BillingDashboard />} />\n          <Route path="/payments" element={<Payments />} />'
    )
    ap.write_text(a, encoding="utf-8")
    print("   added /payments route")

# ─── 4. Build & Push ───────────────────────────────────────────────────
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

print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "feat(finance): add payments ledger page", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")