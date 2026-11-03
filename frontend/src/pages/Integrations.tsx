import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { 
  MessageSquare, Smartphone, Save, Loader2, Key, 
  CreditCard, Building2, CheckCircle2 
} from "lucide-react";

export default function Integrations() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<"payments" | "comms">("payments");
  const [saved, setSaved] = useState(false);

  const [form, setForm] = useState({
    // Payments
    momo_api_key: "",
    momo_provider: "MTN",
    stripe_public_key: "",
    stripe_secret_key: "",
    // Comms
    sms_api_key: "",
    sms_sender_id: "",
    whatsapp_phone_id: "",
    whatsapp_token: "",
  });

  const { data, isLoading } = useQuery({
    queryKey: ["integration-settings"],
    queryFn: async () => (await api.get("/integrations/settings/")).data,
  });

  useEffect(() => {
    if (data) setForm((prev) => ({ ...prev, ...data }));
  }, [data]);

  const save = useMutation({
    mutationFn: async () => (await api.put("/integrations/settings/", form)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integration-settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  if (isLoading) return <div className="p-8 text-slate-500">Loading settings...</div>;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Integrations & API Keys</h1>
          <p className="text-sm text-slate-500 mt-1">Manage payment gateways and patient communication channels.</p>
        </div>
        <button 
          onClick={() => save.mutate()} 
          disabled={save.isPending}
          className="flex items-center gap-2 bg-sky-600 hover:bg-sky-700 text-white px-5 py-2.5 rounded-lg font-medium transition disabled:opacity-50 shadow-sm"
        >
          {save.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
          Save All Settings
        </button>
      </div>

      {saved && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-lg flex items-center gap-2 text-sm font-medium">
          <CheckCircle2 className="h-5 w-5" /> Settings saved successfully. Updates are live.
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 border-b">
        <button 
          onClick={() => setActiveTab("payments")} 
          className={`pb-3 px-2 font-medium flex items-center gap-2 transition ${activeTab === "payments" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500 hover:text-slate-700"}`}
        >
          <CreditCard className="h-4 w-4" /> Payment Gateways
        </button>
        <button 
          onClick={() => setActiveTab("comms")} 
          className={`pb-3 px-2 font-medium flex items-center gap-2 transition ${activeTab === "comms" ? "border-b-2 border-sky-600 text-sky-700" : "text-slate-500 hover:text-slate-700"}`}
        >
          <MessageSquare className="h-4 w-4" /> Patient Communication
        </button>
      </div>

      {/* PAYMENTS TAB */}
      {activeTab === "payments" && (
        <div className="grid md:grid-cols-2 gap-6">
          {/* Mobile Money */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-amber-100 p-2 rounded-lg"><Smartphone className="h-5 w-5 text-amber-600" /></div>
              <div>
                <h2 className="text-lg font-semibold text-slate-800">Mobile Money</h2>
                <p className="text-xs text-slate-500">MTN, Airtel, Zamtel via Lipila/MoneyUnify</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Gateway API Key</label>
                <input type="password" name="momo_api_key" value={form.momo_api_key} onChange={handleChange}
                       placeholder="e.g., lipila_test_..."
                       className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 outline-none transition" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Default Provider</label>
                <select name="momo_provider" value={form.momo_provider} onChange={handleChange}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 outline-none transition bg-white">
                  <option value="MTN">MTN Mobile Money</option>
                  <option value="Airtel">Airtel Money</option>
                  <option value="Zamtel">Zamtel Kwacha</option>
                </select>
              </div>
            </div>
          </div>

          {/* Stripe */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-indigo-100 p-2 rounded-lg"><CreditCard className="h-5 w-5 text-indigo-600" /></div>
              <div>
                <h2 className="text-lg font-semibold text-slate-800">Stripe Card Payments</h2>
                <p className="text-xs text-slate-500">Visa, Mastercard, International</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Publishable Key</label>
                <input type="text" name="stripe_public_key" value={form.stripe_public_key} onChange={handleChange}
                       placeholder="pk_live_..."
                       className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none transition" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Secret Key</label>
                <input type="password" name="stripe_secret_key" value={form.stripe_secret_key} onChange={handleChange}
                       placeholder="sk_live_..."
                       className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none transition" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* COMMS TAB */}
      {activeTab === "comms" && (
        <div className="grid md:grid-cols-2 gap-6">
          {/* SMS Settings */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-sky-100 p-2 rounded-lg"><Smartphone className="h-5 w-5 text-sky-600" /></div>
              <div>
                <h2 className="text-lg font-semibold text-slate-800">SMS Gateway</h2>
                <p className="text-xs text-slate-500">Africa's Talking</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
                <input type="password" name="sms_api_key" value={form.sms_api_key} onChange={handleChange}
                       placeholder="atsk_..."
                       className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none transition" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Sender ID / Shortcode</label>
                <input type="text" name="sms_sender_id" value={form.sms_sender_id} onChange={handleChange}
                       placeholder="e.g., NIMBUS"
                       className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none transition" />
              </div>
            </div>
          </div>

          {/* WhatsApp Settings */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-emerald-100 p-2 rounded-lg"><MessageSquare className="h-5 w-5 text-emerald-600" /></div>
              <div>
                <h2 className="text-lg font-semibold text-slate-800">WhatsApp Business</h2>
                <p className="text-xs text-slate-500">Meta Cloud API</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Phone Number ID</label>
                <input type="text" name="whatsapp_phone_id" value={form.whatsapp_phone_id} onChange={handleChange}
                       placeholder="e.g., 1045..."
                       className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none transition" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Permanent Access Token</label>
                <input type="password" name="whatsapp_token" value={form.whatsapp_token} onChange={handleChange}
                       placeholder="EAAL..."
                       className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none transition" />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
