#!/usr/bin/env python3
"""
add_finance_integrations.py
  - Allows Finance Manager to manage MoMo/Stripe/PayPal settings.
  - Updates Billing Dashboard to dynamically load active payment gateways.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

FRONTEND = ROOT / "frontend"

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Grant Finance Manager permissions to Config ViewSets ──
print("==> Patching api/views.py (Permissions)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Allow finance_manager to manage MobileMoneyConfig
v = v.replace(
    'class MobileMoneyConfigViewSet(viewsets.ModelViewSet):\n    queryset = MobileMoneyConfig.objects.all()\n    serializer_class = MobileMoneyConfigSerializer\n    permission_classes = [require_roles("admin")]',
    'class MobileMoneyConfigViewSet(viewsets.ModelViewSet):\n    queryset = MobileMoneyConfig.objects.all()\n    serializer_class = MobileMoneyConfigSerializer\n    permission_classes = [require_roles("admin", "finance_manager")]'
)

# Allow finance_manager to manage PaymentGatewayConfig
v = v.replace(
    'class PaymentGatewayConfigViewSet(viewsets.ModelViewSet):\n    queryset = PaymentGatewayConfig.objects.all()\n    serializer_class = PaymentGatewayConfigSerializer\n    permission_classes = [require_roles("admin")]',
    'class PaymentGatewayConfigViewSet(viewsets.ModelViewSet):\n    queryset = PaymentGatewayConfig.objects.all()\n    serializer_class = PaymentGatewayConfigSerializer\n    permission_classes = [require_roles("admin", "finance_manager")]'
)

# Fix the get_queryset methods to use all_objects and tenant_id filter
v = v.replace(
    'return qs.filter(tenant=self.request.user.tenant)',
    'return qs.filter(tenant_id=self.request.user.tenant_id)'
)

vp.write_text(v, encoding="utf-8")
print("   patched backend permissions")

# ─── 2. FRONTEND: Create Integrations Page ─────────────────────────────
print("==> Creating Integrations.tsx")
write_frontend("src/pages/Integrations.tsx", '''\
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function Integrations() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"momo" | "gateway">("momo");

  const momoConfigs = useQuery({
    queryKey: ["momo-configs"],
    queryFn: async () => (await api.get<Paginated<any>>("/mobile-money-configs/")).data.results,
  });

  const gatewayConfigs = useQuery({
    queryKey: ["gateway-configs"],
    queryFn: async () => (await api.get<Paginated<any>>("/payment-gateway-configs/")).data.results,
  });

  const createMomo = useMutation({
    mutationFn: async (payload: any) => await api.post("/mobile-money-configs/", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["momo-configs"] }),
  });

  const createGateway = useMutation({
    mutationFn: async (payload: any) => await api.post("/payment-gateway-configs/", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["gateway-configs"] }),
  });

  const testConnection = useMutation({
    mutationFn: async ({ id, type }: { id: number, type: "momo" | "gateway" }) => {
      const endpoint = type === "momo" ? `/mobile-money-configs/${id}/test-connection/` : `/payment-gateway-configs/${id}/test-connection/`;
      await api.post(endpoint);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["momo-configs"] });
      qc.invalidateQueries({ queryKey: ["gateway-configs"] });
    }
  });

  function onMomoSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createMomo.mutate({
      provider: fd.get("provider"),
      environment: fd.get("environment"),
      merchant_code: fd.get("merchant_code"),
      api_key: fd.get("api_key"),
      api_secret: fd.get("api_secret"),
      is_active: true,
    });
  }

  function onGatewaySubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createGateway.mutate({
      provider: fd.get("provider"),
      environment: fd.get("environment"),
      publishable_key: fd.get("publishable_key"),
      secret_key: fd.get("secret_key"),
      is_active: true,
    });
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Payment Integrations</h1>
          <p className="text-sm text-slate-500 mt-1">Configure MoMo and Card gateways.</p>
        </div>
      </div>

      <div className="flex gap-4 border-b">
        <button onClick={() => setTab("momo")} className={`pb-2 px-1 font-medium ${tab === "momo" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Mobile Money</button>
        <button onClick={() => setTab("gateway")} className={`pb-2 px-1 font-medium ${tab === "gateway" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500"}`}>Card Gateways (Stripe/PayPal)</button>
      </div>

      {tab === "momo" && (
        <div className="space-y-6">
          <form onSubmit={onMomoSubmit} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
            <h2 className="font-bold text-lg">Add Mobile Money Config</h2>
            <div className="grid grid-cols-2 gap-4">
              <label className="text-sm"><span className="text-slate-600">Provider</span>
                <select name="provider" required className="mt-1 w-full border rounded-lg px-3 py-2">
                  <option value="mtn_momo">MTN MoMo</option>
                  <option value="airtel_money">Airtel Money</option>
                  <option value="zamtel_kwacha">Zamtel Kwacha</option>
                </select>
              </label>
              <label className="text-sm"><span className="text-slate-600">Environment</span>
                <select name="environment" required className="mt-1 w-full border rounded-lg px-3 py-2">
                  <option value="sandbox">Sandbox</option>
                  <option value="production">Production</option>
                </select>
              </label>
              <label className="text-sm"><span className="text-slate-600">Merchant Code</span><input name="merchant_code" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
              <label className="text-sm"><span className="text-slate-600">API Key</span><input name="api_key" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
              <label className="text-sm col-span-2"><span className="text-slate-600">API Secret</span><input name="api_secret" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            </div>
            <button type="submit" disabled={createMomo.isPending} className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700">Save MoMo Config</button>
          </form>
          
          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b"><tr><th className="text-left px-4 py-2">Provider</th><th className="text-left px-4 py-2">Env</th><th className="text-left px-4 py-2">Merchant</th><th className="text-right px-4 py-2">Action</th></tr></thead>
              <tbody className="divide-y">
                {momoConfigs.data?.map((c: any) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3 font-medium capitalize">{c.provider.replace("_", " ")}</td>
                    <td className="px-4 py-3">{c.environment}</td>
                    <td className="px-4 py-3">{c.merchant_code}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => testConnection.mutate({ id: c.id, type: "momo" })} className="text-xs bg-slate-100 hover:bg-slate-200 px-3 py-1 rounded">Test Connection</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "gateway" && (
        <div className="space-y-6">
          <form onSubmit={onGatewaySubmit} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
            <h2 className="font-bold text-lg">Add Card Gateway Config</h2>
            <div className="grid grid-cols-2 gap-4">
              <label className="text-sm"><span className="text-slate-600">Provider</span>
                <select name="provider" required className="mt-1 w-full border rounded-lg px-3 py-2">
                  <option value="stripe">Stripe</option>
                  <option value="paypal">PayPal</option>
                </select>
              </label>
              <label className="text-sm"><span className="text-slate-600">Environment</span>
                <select name="environment" required className="mt-1 w-full border rounded-lg px-3 py-2">
                  <option value="sandbox">Sandbox</option>
                  <option value="production">Production</option>
                </select>
              </label>
              <label className="text-sm col-span-2"><span className="text-slate-600">Publishable Key / Client ID</span><input name="publishable_key" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
              <label className="text-sm col-span-2"><span className="text-slate-600">Secret Key</span><input name="secret_key" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            </div>
            <button type="submit" disabled={createGateway.isPending} className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700">Save Gateway Config</button>
          </form>

          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b"><tr><th className="text-left px-4 py-2">Provider</th><th className="text-left px-4 py-2">Env</th><th className="text-right px-4 py-2">Action</th></tr></thead>
              <tbody className="divide-y">
                {gatewayConfigs.data?.map((c: any) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3 font-medium capitalize">{c.provider}</td>
                    <td className="px-4 py-3">{c.environment}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => testConnection.mutate({ id: c.id, type: "gateway" })} className="text-xs bg-slate-100 hover:bg-slate-200 px-3 py-1 rounded">Test Connection</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
''')

# ─── 3. FRONTEND: Update Billing Dashboard to use Dynamic Methods ──────
print("==> Updating BillingDashboard.tsx")
bp = FRONTEND / "src" / "pages" / "BillingDashboard.tsx"
b = bp.read_text(encoding="utf-8")

# Add queries for active configurations
if "const momoConfigs = useQuery" not in b:
    b = b.replace(
        'const visits = useQuery({',
        '''const momoConfigs = useQuery({
    queryKey: ["momo-configs-active"],
    queryFn: async () => (await api.get<Paginated<any>>("/mobile-money-configs/?is_active=true")).data.results,
  });

  const gatewayConfigs = useQuery({
    queryKey: ["gateway-configs-active"],
    queryFn: async () => (await api.get<Paginated<any>>("/payment-gateway-configs/?is_active=true")).data.results,
  });

  const visits = useQuery({'''
    )

# Update payment mutation to pass config IDs
old_payment = '''  function onPayment(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!invoice.data) return;
    const fd = new FormData(e.currentTarget);
    recordPayment.mutate({
      invoice: invoice.data.id,
      amount: String(fd.get("amount")),
      method: String(fd.get("method")),
      reference: String(fd.get("reference") || ""),
    });
  }'''

new_payment = '''  function onPayment(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!invoice.data) return;
    const fd = new FormData(e.currentTarget);
    const methodVal = String(fd.get("method"));
    
    // Parse out the config ID if the method uses one (e.g., "mobile_money:1")
    const [method, configIdStr] = methodVal.split(":");
    const configId = configIdStr ? parseInt(configIdStr) : null;

    const payload: any = {
      invoice: invoice.data.id,
      amount: String(fd.get("amount")),
      method: method,
      reference: String(fd.get("reference") || ""),
    };

    if (method === "mobile_money" && configId) {
      payload.mobile_money_config = configId;
    } else if ((method === "card" || method === "stripe" || method === "paypal") && configId) {
      payload.payment_gateway_config = configId;
    }

    recordPayment.mutate(payload);
  }'''

if old_payment in b:
    b = b.replace(old_payment, new_payment)

# Update the payment select dropdown in the UI
old_select = '''                    <label className="text-xs">
                      <span className="text-slate-500">Method</span>
                      <select name="method" className="w-full mt-1 border rounded px-2 py-1.5">
                        <option value="cash">Cash</option>
                        <option value="mobile_money">Mobile Money</option>
                        <option value="insurance">Insurance</option>
                      </select>
                    </label>'''

new_select = '''                    <label className="text-xs">
                      <span className="text-slate-500">Method</span>
                      <select name="method" className="w-full mt-1 border rounded px-2 py-1.5">
                        <option value="cash">Cash</option>
                        <option value="insurance">Insurance</option>
                        
                        {/* Dynamic Mobile Money Options */}
                        {momoConfigs.data?.map((c: any) => (
                          <option key={`momo-${c.id}`} value={`mobile_money:${c.id}`}>
                            {c.provider.replace("_", " ")} {c.display_name ? `(${c.display_name})` : ""}
                          </option>
                        ))}
                        
                        {/* Dynamic Gateway Options */}
                        {gatewayConfigs.data?.map((c: any) => (
                          <option key={`gw-${c.id}`} value={`card:${c.id}`}>
                            {c.provider.charAt(0).toUpperCase() + c.provider.slice(1)} (Card)
                          </option>
                        ))}
                      </select>
                    </label>'''

if old_select in b:
    b = b.replace(old_select, new_select)
    bp.write_text(b, encoding="utf-8")
    print("   patched BillingDashboard with dynamic payment methods")

# ─── 4. FRONTEND: Navigation & Routing ─────────────────────────────────
print("==> Updating Layout and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Integrations" not in l:
    l = l.replace(
        '{isClinicalStaff && (user?.role === "accountant" || user?.role === "finance_manager" || user?.role === "admin") && (\n              <NavLink to="/accounting" className={linkClass}>Accounting</NavLink>\n            )}',
        '{isClinicalStaff && (user?.role === "accountant" || user?.role === "finance_manager" || user?.role === "admin") && (\n              <>\n                <NavLink to="/accounting" className={linkClass}>Accounting</NavLink>\n                <NavLink to="/integrations" className={linkClass}>Integrations</NavLink>\n              </>\n            )}'
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
app = ap.read_text(encoding="utf-8")
if "Integrations" not in app:
    app = app.replace(
        'import AccountingDashboard from "./pages/AccountingDashboard";',
        'import AccountingDashboard from "./pages/AccountingDashboard";\nimport Integrations from "./pages/Integrations";'
    )
    app = app.replace(
        '<Route path="/accounting" element={<AccountingDashboard />} />',
        '<Route path="/accounting" element={<AccountingDashboard />} />\n          <Route path="/integrations" element={<Integrations />} />'
    )
    ap.write_text(app, encoding="utf-8")

print("==> Done. Push to GitHub and redeploy both services.")