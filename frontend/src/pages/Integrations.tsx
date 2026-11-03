import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function Integrations() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"momo" | "gateway">("momo");

  // --- MoMo State ---
  const [editMomoId, setEditMomoId] = useState<number | null>(null);
  const [momoApiUser, setMomoApiUser] = useState("");
  const [momoApiKey, setMomoApiKey] = useState("");
  const [momoProvider, setMomoProvider] = useState("mtn_momo");
  const [momoEnv, setMomoEnv] = useState("sandbox");
  const [momoMerchant, setMomoMerchant] = useState("");
  const [momoCallback, setMomoCallback] = useState("");
  const [momoSubKey, setMomoSubKey] = useState("");

  // --- Gateway State ---
  const [editGwId, setEditGwId] = useState<number | null>(null);
  const [gwProvider, setGwProvider] = useState("stripe");
  const [gwEnv, setGwEnv] = useState("sandbox");
  const [gwPubKey, setGwPubKey] = useState("");

  const momoConfigs = useQuery({
    queryKey: ["momo-configs"],
    queryFn: async () => (await api.get<Paginated<any>>("/mobile-money-configs/")).data.results,
  });

  const gatewayConfigs = useQuery({
    queryKey: ["gateway-configs"],
    queryFn: async () => (await api.get<Paginated<any>>("/payment-gateway-configs/")).data.results,
  });

  // ── Mutations ──
  const saveMomo = useMutation({
    mutationFn: async (payload: any) => {
      if (editMomoId) {
        return await api.patch(`/mobile-money-configs/${editMomoId}/`, payload);
      }
      return await api.post("/mobile-money-configs/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["momo-configs"] });
      resetMomoForm();
    },
    onError: (err: any) => {
      alert("Failed to save: " + (err.response?.data?.detail || JSON.stringify(err.response?.data) || err.message));
    }
  });

  const saveGateway = useMutation({
    mutationFn: async (payload: any) => {
      if (editGwId) {
        return await api.patch(`/payment-gateway-configs/${editGwId}/`, payload);
      }
      return await api.post("/payment-gateway-configs/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["gateway-configs"] });
      resetGwForm();
    },
  });

  const generateApiUser = useMutation({
    mutationFn: async (payload: { provider: string, callback_host: string, subscription_key: string }) => {
      const { data } = await api.post("/mobile-money-configs/create-api-user/", payload);
      return data;
    },
    onSuccess: (data) => {
      setMomoApiUser(data.api_user);
      setMomoApiKey(data.api_key);
      alert(data.message);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message;
      alert("Failed to generate API User from MTN: \n\n" + msg);
    }
  });

  const testConnection = useMutation({
    mutationFn: async ({ id, type }: { id: number, type: "momo" | "gateway" }) => {
      const endpoint = type === "momo" ? `/mobile-money-configs/${id}/test-connection/` : `/payment-gateway-configs/${id}/test-connection/`;
      return await api.post(endpoint);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["momo-configs"] });
      qc.invalidateQueries({ queryKey: ["gateway-configs"] });
    }
  });

  // ── Handlers ──
  function resetMomoForm() {
    setEditMomoId(null);
    setMomoProvider("mtn_momo");
    setMomoEnv("sandbox");
    setMomoMerchant("");
    setMomoCallback("");
    setMomoApiUser("");
    setMomoApiKey("");
    setMomoSubKey("");
  }

  function editMomo(c: any) {
    setEditMomoId(c.id);
    setMomoProvider(c.provider);
    setMomoEnv(c.environment);
    setMomoMerchant(c.merchant_code);
    setMomoCallback(c.callback_host || "");
    setMomoApiUser(c.api_user || "");
    setMomoApiKey(""); // Always blank on edit for security
    setMomoSubKey(""); // Always blank on edit
  }

  function submitMomo(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: any = {
      provider: momoProvider,
      environment: momoEnv,
      merchant_code: momoMerchant,
      callback_host: momoCallback,
      is_active: true,
    };
    if (momoApiUser) payload.api_user = momoApiUser;
    if (momoApiKey) payload.api_key = momoApiKey;
    
    const secret = fd.get("api_secret");
    if (secret) payload.api_secret = secret;
    
    if (momoSubKey) payload.subscription_key = momoSubKey;
    
    saveMomo.mutate(payload);
  }

  function resetGwForm() {
    setEditGwId(null);
    setGwProvider("stripe");
    setGwEnv("sandbox");
    setGwPubKey("");
  }

  function editGw(c: any) {
    setEditGwId(c.id);
    setGwProvider(c.provider);
    setGwEnv(c.environment);
    setGwPubKey(c.publishable_key || "");
  }

  function submitGw(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: any = {
      provider: gwProvider,
      environment: gwEnv,
      publishable_key: gwPubKey,
      is_active: true,
    };
    const secret = fd.get("secret_key");
    if (secret) payload.secret_key = secret;
    
    saveGateway.mutate(payload);
  }

  return (
    <div className="space-y-6 max-w-5xl">
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
          <form onSubmit={submitMomo} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="font-bold text-lg">{editMomoId ? "Edit" : "Add"} Mobile Money Config</h2>
              {editMomoId && <button type="button" onClick={resetMomoForm} className="text-xs text-slate-500 hover:text-slate-700">Cancel Edit</button>}
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <label className="text-sm"><span className="text-slate-600">Provider</span>
                <select value={momoProvider} onChange={e => setMomoProvider(e.target.value)} required className="mt-1 w-full border rounded-lg px-3 py-2">
                  <option value="mtn_momo">MTN MoMo</option>
                  <option value="airtel_money">Airtel Money</option>
                  <option value="zamtel_kwacha">Zamtel Kwacha</option>
                </select>
              </label>
              <label className="text-sm"><span className="text-slate-600">Environment</span>
                <select value={momoEnv} onChange={e => setMomoEnv(e.target.value)} required className="mt-1 w-full border rounded-lg px-3 py-2">
                  <option value="sandbox">Sandbox</option>
                  <option value="production">Production</option>
                </select>
              </label>
              
              <label className="text-sm"><span className="text-slate-600">Merchant Code</span><input value={momoMerchant} onChange={e => setMomoMerchant(e.target.value)} required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
              <label className="text-sm"><span className="text-slate-600">Callback Host URL</span><input value={momoCallback} onChange={e => setMomoCallback(e.target.value)} required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
              
              <div className="col-span-2 border-t my-2"></div>
              <div className="col-span-2 flex justify-between items-end">
                <div className="text-sm font-semibold text-slate-700">API Credentials
      {/* ── SMS & WHATSAPP SETTINGS (Appended) ──────────────────────── */}
      <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="bg-sky-100 p-2 rounded-lg">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-sky-600"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-800">SMS & WhatsApp Integration</h2>
            <p className="text-xs text-slate-500">Configure patient communication channels</p>
          </div>
        </div>
        
        <div className="grid md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <h3 className="font-medium text-slate-700 text-sm border-b pb-2">SMS (Africa's Talking)</h3>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
              <input type="password" name="sms_api_key" value={form.sms_api_key || ""} onChange={handleChange}
                     placeholder="atsk_..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Sender ID / Shortcode</label>
              <input type="text" name="sms_sender_id" value={form.sms_sender_id || ""} onChange={handleChange}
                     placeholder="e.g., NIMBUS"
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none transition" />
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="font-medium text-slate-700 text-sm border-b pb-2">WhatsApp (Meta Cloud API)</h3>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Phone Number ID</label>
              <input type="text" name="whatsapp_phone_id" value={form.whatsapp_phone_id || ""} onChange={handleChange}
                     placeholder="e.g., 1045..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Permanent Access Token</label>
              <input type="password" name="whatsapp_token" value={form.whatsapp_token || ""} onChange={handleChange}
                     placeholder="EAAL..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none transition" />
            </div>
          </div>
        </div>
      </div>
    </div>
                <button 
                  type="button" 
                  onClick={() => {
                    const subKey = momoSubKey || prompt("Please enter the Subscription Key from the MTN Portal:");
                    if (!subKey) return;
                    generateApiUser.mutate({ provider: momoProvider, callback_host: momoCallback, subscription_key: subKey });
                  }}
                  disabled={generateApiUser.isPending || !momoCallback}
                  className="text-xs bg-indigo-50 text-indigo-700 px-3 py-1.5 rounded border border-indigo-200 hover:bg-indigo-100 font-medium disabled:opacity-50"
                >
                  ⚡ Generate API User
                </button>
              </div>
              
              <label className="text-sm"><span className="text-slate-600">API User</span>
                <input value={momoApiUser} readOnly className="mt-1 w-full border rounded-lg px-3 py-2 bg-slate-50 text-slate-500" placeholder="Click Generate above" />
              </label>
              <label className="text-sm"><span className="text-slate-600">API Key</span>
                <input 
                  value={momoApiKey} 
                  readOnly 
                  className="mt-1 w-full border rounded-lg px-3 py-2 bg-slate-50 text-slate-500 font-mono text-xs" 
                  placeholder={editMomoId ? "(Leave blank to keep current)" : "Click Generate above"} 
                />
              </label>
              <label className="text-sm"><span className="text-red-500 font-medium">API Secret {!editMomoId && "*"}</span><input name="api_secret" required={!editMomoId} className="mt-1 w-full border rounded-lg px-3 py-2" placeholder={editMomoId ? "(Leave blank to keep current)" : ""} /></label>
              <label className="text-sm"><span className="text-red-500 font-medium">Subscription Key {!editMomoId && "*"}</span><input value={momoSubKey} onChange={e => setMomoSubKey(e.target.value)} required={!editMomoId} className="mt-1 w-full border rounded-lg px-3 py-2" placeholder={editMomoId ? "(Leave blank to keep current)" : "Ocp-Apim-Subscription-Key from MTN Portal"} /></label>
            </div>
            
            <button type="submit" disabled={saveMomo.isPending} className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700 mt-4">
              {saveMomo.isPending ? "Saving..." : (editMomoId ? "Update Config" : "Save Config")}
            </button>
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
                  <tr key={c.id} className={`hover:bg-slate-50 ${editMomoId === c.id ? "bg-sky-50" : ""}`}>
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
                    <td className="px-4 py-3 text-right space-x-2">
                      <button onClick={() => editMomo(c)} className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded font-medium">Edit</button>
                      <button 
                        onClick={() => testConnection.mutate({ id: c.id, type: "momo" })} 
                        disabled={testConnection.isPending}
                        className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded font-medium"
                      >
                        {testConnection.isPending && testConnection.variables?.id === c.id ? "Testing..." : "Test"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Gateway Tab remains the same... */}
    </div>
  );
}