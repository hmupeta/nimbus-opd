import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { MessageSquare, Smartphone, Save, Loader2, Key } from "lucide-react";

export default function Integrations() {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    sms_api_key: "",
    sms_sender_id: "",
    whatsapp_phone_id: "",
    whatsapp_token: "",
  });
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["integration-settings"],
    queryFn: async () => (await api.get("/integrations/settings/")).data,
  });

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const save = useMutation({
    mutationFn: async () => (await api.put("/integrations/settings/", form)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integration-settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  if (isLoading) return <div className="p-8">Loading settings...</div>;

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Integrations & API Keys</h1>
        <p className="text-sm text-slate-500 mt-1">Manage your SMS and WhatsApp communication settings for this clinic.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* SMS Settings */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-sky-100 p-2 rounded-lg"><Smartphone className="h-5 w-5 text-sky-600" /></div>
            <h2 className="text-lg font-semibold text-slate-800">SMS Settings (Africa's Talking)</h2>
          </div>
          <div className="space-y-4">
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
        </div>

        {/* WhatsApp Settings */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-emerald-100 p-2 rounded-lg"><MessageSquare className="h-5 w-5 text-emerald-600" /></div>
            <h2 className="text-lg font-semibold text-slate-800">WhatsApp Settings (Meta Cloud API)</h2>
          </div>
          <div className="space-y-4">
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

      <div className="flex items-center gap-4 pt-4">
        <button onClick={() => save.mutate()} disabled={save.isPending}
                className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-6 py-2.5 rounded-lg font-medium transition disabled:opacity-50">
          {save.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
          Save Settings
        </button>
        {saved && <span className="text-emerald-600 text-sm font-medium flex items-center gap-1"><Key className="h-4 w-4"/> Settings saved securely.</span>}
      </div>
    </div>
  );
}
