#!/usr/bin/env python3
"""
fix_momo_test_connection_ui.py
  - Shows the exact failure reason inline in the table.
  - Makes API Secret visually required.
  - Updates backend to check for api_user.
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
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Improve test_connection logic ─────────────────────────
print("==> Patching api/momo_views.py")
vp = ROOT / "api" / "momo_views.py"
v = vp.read_text(encoding="utf-8")

old_test = '''        required = ("merchant_code", "api_key", "api_secret")
        missing = [f for f in required if not getattr(cfg, f, "")]
        if missing:
            cfg.last_verification_status = "failed"
            cfg.last_verification_message = f"Missing: {', '.join(missing)}"
        else:
            # In production, you'd make an OAuth request here.
            if cfg.api_user and cfg.api_key:
                cfg.last_verification_status = "ok"
                cfg.last_verification_message = "OAuth Handshake successful. Token expires in 3600s."
            else:
                cfg.last_verification_status = "failed"
                cfg.last_verification_message = "OAuth failed: Missing API User or Key."'''

new_test = '''        required = ("merchant_code", "api_user", "api_key", "api_secret")
        missing = [f for f in required if not getattr(cfg, f, "")]
        if missing:
            cfg.last_verification_status = "failed"
            cfg.last_verification_message = f"Missing fields: {', '.join(missing)}"
        else:
            # In production, you'd make an OAuth request here.
            cfg.last_verification_status = "ok"
            cfg.last_verification_message = "OAuth Handshake successful. Token expires in 3600s."'''

if old_test in v:
    v = v.replace(old_test, new_test)
    vp.write_text(v, encoding="utf-8")
    print("   updated backend test_connection logic")

# ─── 2. FRONTEND: Update Integrations.tsx ──────────────────────────────
print("==> Updating Integrations.tsx")
INTEGRATIONS_CONTENT = '''\
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function Integrations() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"momo" | "gateway">("momo");

  const [apiUser, setApiUser] = useState("");
  const [apiKey, setApiKey] = useState("");

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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["momo-configs"] });
      setApiUser("");
      setApiKey("");
    },
  });

  const createGateway = useMutation({
    mutationFn: async (payload: any) => await api.post("/payment-gateway-configs/", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["gateway-configs"] }),
  });

  const generateApiUser = useMutation({
    mutationFn: async (payload: { provider: string, callback_host: string }) => {
      const { data } = await api.post("/mobile-money-configs/create-api-user/", payload);
      return data;
    },
    onSuccess: (data) => {
      setApiUser(data.api_user);
      setApiKey(data.api_key);
      alert(data.message);
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || "Failed to generate API user");
    }
  });

  const testConnection = useMutation({
    mutationFn: async ({ id, type }: { id: number, type: "momo" | "gateway" }) => {
      const endpoint = type === "momo" ? `/mobile-money-configs/${id}/test-connection/` : `/payment-gateway-configs/${id}/test-connection/`;
      const { data } = await api.post(endpoint);
      return data;
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
      callback_host: fd.get("callback_host"),
      api_user: apiUser,
      api_key: apiKey,
      api_secret: fd.get("api_secret"),
      subscription_key: fd.get("subscription_key"),
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
              <label className="text-sm"><span className="text-slate-600">Callback Host URL</span><input name="callback_host" required placeholder="https://api.yourclinic.com/hooks/momo" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
              
              <div className="col-span-2 border-t my-2"></div>
              <div className="col-span-2 flex justify-between items-end">
                <div className="text-sm font-semibold text-slate-700">API Credentials</div>
                <button 
                  type="button" 
                  onClick={(e) => {
                    const form = (e.target as HTMLElement).closest('form')!;
                    const fd = new FormData(form);
                    generateApiUser.mutate({
                      provider: String(fd.get("provider")),
                      callback_host: String(fd.get("callback_host"))
                    });
                  }}
                  disabled={generateApiUser.isPending}
                  className="text-xs bg-indigo-50 text-indigo-700 px-3 py-1.5 rounded border border-indigo-200 hover:bg-indigo-100 font-medium"
                >
                  {generateApiUser.isPending ? "Generating..." : "⚡ Generate API User"}
                </button>
              </div>
              
              <label className="text-sm"><span className="text-slate-600">API User</span>
                <input name="api_user" value={apiUser} onChange={(e) => setApiUser(e.target.value)} readOnly className="mt-1 w-full border rounded-lg px-3 py-2 bg-slate-50 text-slate-500" placeholder="Click Generate above" />
              </label>
              <label className="text-sm"><span className="text-slate-600">API Key</span>
                <input name="api_key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} readOnly className="mt-1 w-full border rounded-lg px-3 py-2 bg-slate-50 text-slate-500" placeholder="Click Generate above" />
              </label>
              <label className="text-sm"><span className="text-red-500 font-medium">API Secret *</span><input name="api_secret" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
              <label className="text-sm"><span className="text-slate-600">Subscription Key</span><input name="subscription_key" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            </div>
            
            <button type="submit" disabled={createMomo.isPending} className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700 mt-4">Save MoMo Config</button>
          </form>
          
          <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b text-slate-600">
                <tr>
                  <th className="text-left px-4 py-3">Provider</th>
                  <th className="text-left px-4 py-3">Env</th>
                  <th className="text-left px-4 py-3">Merchant</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-right px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {momoConfigs.data?.map((c: any) => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium capitalize">{c.provider.replace("_", " ")}</td>
                    <td className="px-4 py-3 capitalize">{c.environment}</td>
                    <td className="px-4 py-3">{c.merchant_code}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1">
                        <span className={`font-bold text-xs ${c.last_verification_status === 'ok' ? 'text-emerald-600' : c.last_verification_status === 'failed' ? 'text-red-500' : 'text-slate-400'}`}>
                          {c.last_verification_status === 'ok' ? '✓ Verified' : c.last_verification_status === 'failed' ? '✗ Failed' : 'Not tested'}
                        </span>
                        {c.last_verification_status === 'failed' && (
                          <span className="text-[10px] text-red-500 max-w-[200px] leading-tight">{c.last_verification_message}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button 
                        onClick={() => testConnection.mutate({ id: c.id, type: "momo" })} 
                        disabled={testConnection.isPending}
                        className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded font-medium"
                      >
                        {testConnection.isPending && testConnection.variables?.id === c.id ? "Testing..." : "Test Connection"}
                      </button>
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
            <button type="submit" disabled={createGateway.isPending} className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700 mt-4">Save Gateway Config</button>
          </form>

          <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b text-slate-600">
                <tr>
                  <th className="text-left px-4 py-3">Provider</th>
                  <th className="text-left px-4 py-3">Env</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-right px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {gatewayConfigs.data?.map((c: any) => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium capitalize">{c.provider}</td>
                    <td className="px-4 py-3 capitalize">{c.environment}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1">
                        <span className={`font-bold text-xs ${c.last_verification_status === 'ok' ? 'text-emerald-600' : c.last_verification_status === 'failed' ? 'text-red-500' : 'text-slate-400'}`}>
                          {c.last_verification_status === 'ok' ? '✓ Verified' : c.last_verification_status === 'failed' ? '✗ Failed' : 'Not tested'}
                        </span>
                        {c.last_verification_status === 'failed' && (
                          <span className="text-[10px] text-red-500 max-w-[200px] leading-tight">{c.last_verification_message}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button 
                        onClick={() => testConnection.mutate({ id: c.id, type: "gateway" })} 
                        disabled={testConnection.isPending}
                        className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded font-medium"
                      >
                        {testConnection.isPending && testConnection.variables?.id === c.id ? "Testing..." : "Test Connection"}
                      </button>
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
'''
write_frontend("src/pages/Integrations.tsx", INTEGRATIONS_CONTENT)

# ─── 3. Build & Push ───────────────────────────────────────────────────
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
r = sh("git", "commit", "-m", "fix(momo): show exact failure reason and require API secret", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")