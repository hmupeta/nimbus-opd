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
