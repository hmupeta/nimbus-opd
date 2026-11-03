import { useState } from "react";
import { MessageCircle, Smartphone, Check, Loader2 } from "lucide-react";
import { api } from "../api/client";

export function NotificationButtons({ paymentId }: { paymentId: number }) {
  const [status, setStatus] = useState<"idle" | "sending_sms" | "sending_wa" | "success">("idle");

  const send = async (method: "sms" | "whatsapp") => {
    setStatus(method === "sms" ? "sending_sms" : "sending_wa");
    try {
      await api.post(`/payments/${paymentId}/send-receipt/`, { method });
      setStatus("success");
      setTimeout(() => setStatus("idle"), 3000);
    } catch (err: any) {
      alert("Failed to send: " + JSON.stringify(err.response?.data || err.message));
      setStatus("idle");
    }
  };

  if (status === "success") {
    return <span className="text-xs font-medium text-emerald-600 flex items-center gap-1"><Check size={14}/> Sent!</span>;
  }

  return (
    <div className="flex gap-1">
      <button 
        onClick={() => send("whatsapp")} 
        disabled={status !== "idle"}
        title="Send WhatsApp Receipt"
        className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded disabled:opacity-50 transition"
      >
        {status === "sending_wa" ? <Loader2 size={16} className="animate-spin" /> : <MessageCircle size={16} />}
      </button>
      <button 
        onClick={() => send("sms")} 
        disabled={status !== "idle"}
        title="Send SMS Receipt"
        className="p-1.5 text-sky-600 hover:bg-sky-50 rounded disabled:opacity-50 transition"
      >
        {status === "sending_sms" ? <Loader2 size={16} className="animate-spin" /> : <Smartphone size={16} />}
      </button>
    </div>
  );
}
