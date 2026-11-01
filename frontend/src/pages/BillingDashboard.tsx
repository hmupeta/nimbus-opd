import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function BillingDashboard() {
  const qc = useQueryClient();
  const [selectedVisit, setSelectedVisit] = useState<number | null>(null);
  
  // MTN MoMo State
  const [momoInvoice, setMomoInvoice] = useState<number | null>(null);
  const [momoRef, setMomoRef] = useState<string | null>(null);
  const [momoPolling, setMomoPolling] = useState(false);
  const [momoPhone, setMomoPhone] = useState("");

  const visits = useQuery({
    queryKey: ["billing-visits"],
    queryFn: async () => (await api.get<Paginated<any>>("/visits/?status=closed")).data,
  });

  const invoice = useQuery({
    queryKey: ["invoice", selectedVisit],
    queryFn: async () => {
      const res = await api.get<Paginated<any>>(`/invoices/?visit=${selectedVisit}`);
      return res.data.results[0] || null;
    },
    enabled: !!selectedVisit,
  });

  const generateInvoice = useMutation({
    mutationFn: async (visitId: number) => {
      const { data } = await api.post(`/visits/${visitId}/generate_invoice/`);
      return data;
    },
    onSuccess: (data: any) => {
      if (data && data.id) {
        qc.setQueryData(["invoice", selectedVisit], data);
      }
    },
  });

  const recordPayment = useMutation({
    mutationFn: async (payload: any) => {
      await api.post("/payments/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoice"] });
      qc.invalidateQueries({ queryKey: ["billing-visits"] });
    },
  });

  const requestMomo = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post("/momo/request/", payload);
      return data;
    },
    onSuccess: (data) => {
      setMomoRef(data.reference_id);
      setMomoPolling(true);
      
      // Start polling every 3 seconds
      const interval = setInterval(async () => {
        try {
          const { data: statusData } = await api.get(`/momo/status/${data.reference_id}/`);
          if (statusData.status === "SUCCESSFUL") {
            clearInterval(interval);
            setMomoPolling(false);
            setMomoInvoice(null);
            qc.invalidateQueries({ queryKey: ["invoice"] });
            qc.invalidateQueries({ queryKey: ["billing-visits"] });
            alert("MTN MoMo Payment Successful!");
          } else if (statusData.status === "FAILED") {
            clearInterval(interval);
            setMomoPolling(false);
            alert("MTN MoMo Payment Failed or Timed Out.");
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 3000);
    },
    onError: (err: any) => {
      alert("Failed to send request: " + (err.response?.data?.detail || err.message));
    }
  });

  function onPayment(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!invoice.data) return;
    const fd = new FormData(e.currentTarget);
    recordPayment.mutate({
      invoice: invoice.data.id,
      amount: String(fd.get("amount")),
      method: String(fd.get("method")),
      reference: String(fd.get("reference") || ""),
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-2xl font-semibold text-slate-800">Reception / Billing</h1>
      
      <div className="grid md:grid-cols-2 gap-6">
        {/* Visit List */}
        <div className="bg-white border rounded-lg overflow-hidden h-fit shadow-sm">
          <div className="bg-slate-50 px-4 py-3 border-b text-sm font-semibold text-slate-600">Ready for Billing (Closed Visits)</div>
          <ul className="divide-y text-sm">
            {visits.data?.results.map((v: any) => (
              <li key={v.id}>
                <button 
                  onClick={() => setSelectedVisit(v.id)} 
                  className={`w-full text-left px-4 py-3 hover:bg-slate-50 ${selectedVisit === v.id ? "bg-sky-50 border-l-4 border-sky-500" : ""}`}
                >
                  <p className="font-medium text-slate-800">{v.patient_name}</p>
                  <p className="text-slate-500 text-xs">{v.visit_no} · {new Date(v.closed_at).toLocaleDateString()}</p>
                </button>
              </li>
            ))}
            {visits.data?.results.length === 0 && (
              <li className="p-4 text-center text-slate-500">No closed visits waiting for billing.</li>
            )}
          </ul>
        </div>

        {/* Invoice Panel */}
        <div className="bg-white border rounded-lg p-6 shadow-sm min-h-[400px]">
          {!selectedVisit ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-slate-400 text-sm">Select a visit to view the bill.</p>
            </div>
          ) : invoice.isLoading ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-slate-500 text-sm">Loading invoice...</p>
            </div>
          ) : !invoice.data ? (
            <div className="flex flex-col h-full items-center justify-center text-center">
              <p className="text-slate-500 text-sm mb-4">No invoice found for this visit.</p>
              <button 
                onClick={() => generateInvoice.mutate(selectedVisit)} 
                disabled={generateInvoice.isPending}
                className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700"
              >
                {generateInvoice.isPending ? "Generating..." : "Generate Invoice"}
              </button>
            </div>
          ) : (
            <div>
              <div className="flex justify-between items-start border-b pb-4 mb-4">
                <div>
                  <h2 className="font-semibold text-lg text-slate-800">{invoice.data.invoice_no}</h2>
                  <p className="text-slate-500 text-sm">{invoice.data.patient_name}</p>
                </div>
                <div className="text-right">
                  <span className={`text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wide ${
                    invoice.data.balance <= 0 ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
                  }`}>
                    {invoice.data.balance <= 0 ? "Paid" : "Unpaid"}
                  </span>
                </div>
              </div>
              
              <ul className="space-y-2 text-sm mb-6">
                {invoice.data.items.map((i: any) => (
                  <li key={i.id} className="flex justify-between text-slate-600">
                    <span>{i.quantity}x {i.description}</span>
                    <span>ZMW {i.total}</span>
                  </li>
                ))}
              </ul>
              
              <div className="flex justify-between font-bold text-lg border-t pt-2 text-slate-800">
                <span>Total</span>
                <span>ZMW {invoice.data.total}</span>
              </div>
              <div className={`flex justify-between font-bold text-lg ${invoice.data.balance > 0 ? "text-red-600" : "text-emerald-600"}`}>
                <span>Balance Due</span>
                <span>ZMW {invoice.data.balance}</span>
              </div>

              {invoice.data.balance > 0 && (
                <form onSubmit={onPayment} className="mt-8 border-t pt-6 space-y-4 bg-slate-50 -mx-6 -mb-6 p-6 rounded-b-lg">
                  <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">Record Manual Payment</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="text-xs">
                      <span className="text-slate-500">Amount (ZMW)</span>
                      <input name="amount" defaultValue={invoice.data.balance} required className="w-full mt-1 border rounded-lg px-3 py-2" />
                    </label>
                    <label className="text-xs">
                      <span className="text-slate-500">Method</span>
                      <select name="method" className="w-full mt-1 border rounded-lg px-3 py-2">
                        <option value="cash">Cash</option>
                        <option value="card">Card</option>
                        <option value="insurance">Insurance</option>
                      </select>
                    </label>
                  </div>
                  <label className="text-xs block">
                    <span className="text-slate-500">Reference / Receipt #</span>
                    <input name="reference" className="w-full mt-1 border rounded-lg px-3 py-2" />
                  </label>
                  <button type="submit" disabled={recordPayment.isPending} className="w-full bg-emerald-600 text-white py-3 rounded-lg font-bold hover:bg-emerald-700 shadow-md mt-2">
                    {recordPayment.isPending ? "Processing..." : "Complete Manual Payment"}
                  </button>
                  
                  <div className="relative flex py-2 items-center">
                    <div className="flex-grow border-t border-slate-200"></div>
                    <span className="flex-shrink-0 mx-4 text-slate-400 text-xs uppercase font-medium">Or</span>
                    <div className="flex-grow border-t border-slate-200"></div>
                  </div>

                  <button 
                    type="button" 
                    onClick={() => setMomoInvoice(invoice.data.id)}
                    className="w-full bg-amber-400 text-amber-900 py-3 rounded-lg font-bold hover:bg-amber-500 shadow-md"
                  >
                    Request MTN MoMo Payment
                  </button>
                </form>
              )}
            </div>
          )}
        </div>
      </div>

      {/* MTN MoMo Modal */}
      {momoInvoice && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white p-6 rounded-xl shadow-xl w-full max-w-sm">
            <h3 className="text-lg font-bold mb-4 text-slate-800">MTN MoMo Payment</h3>
            {!momoRef ? (
              <form onSubmit={(e) => {
                e.preventDefault();
                requestMomo.mutate({ 
                  invoice_id: momoInvoice, 
                  phone_number: momoPhone, 
                  config_id: 1 // Using the first active MoMo config
                });
              }}>
                <label className="block text-sm mb-4">
                  <span className="text-slate-600 font-medium">Customer Phone Number</span>
                  <input value={momoPhone} onChange={e => setMomoPhone(e.target.value)} required placeholder="260966123456" className="mt-1 w-full border rounded-lg px-3 py-2" />
                </label>
                <div className="flex justify-end gap-2">
                  <button type="button" onClick={() => setMomoInvoice(null)} className="px-4 py-2 text-slate-600 font-medium">Cancel</button>
                  <button type="submit" disabled={requestMomo.isPending} className="px-4 py-2 bg-amber-500 text-white rounded-lg font-bold">
                    {requestMomo.isPending ? "Sending..." : "Send Request"}
                  </button>
                </div>
              </form>
            ) : (
              <div className="text-center py-4">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-amber-500 mx-auto mb-4"></div>
                <p className="text-slate-700 font-medium">Waiting for customer to approve...</p>
                <p className="text-sm text-slate-500 mt-1">Please ask the patient to enter their PIN on their phone.</p>
                <p className="text-xs text-slate-400 mt-2 font-mono bg-slate-50 p-1 rounded">Ref: {momoRef}</p>
                <button onClick={() => { setMomoInvoice(null); setMomoRef(null); setMomoPolling(false); }} className="mt-6 text-sm text-slate-500 underline">Cancel</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}