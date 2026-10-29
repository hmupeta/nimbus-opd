import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function BillingDashboard() {
  const qc = useQueryClient();
  const [selectedVisit, setSelectedVisit] = useState<number | null>(null);

  const zReport = useQuery({
    queryKey: ["z-report"],
    queryFn: async () => (await api.get("/analytics/z-report/")).data,
  });

  const momoConfigs = useQuery({
    queryKey: ["momo-configs-active"],
    queryFn: async () => (await api.get<Paginated<any>>("/mobile-money-configs/?is_active=true")).data.results,
  });

  const gatewayConfigs = useQuery({
    queryKey: ["gateway-configs-active"],
    queryFn: async () => (await api.get<Paginated<any>>("/payment-gateway-configs/?is_active=true")).data.results,
  });

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
      // Inject the invoice directly into the React Query cache to render immediately
      if (data && data.id) {
        qc.setQueryData(["invoice", selectedVisit], data);
      }
      // Refresh the list of closed visits (to update any invoice indicators)
      qc.invalidateQueries({ queryKey: ["billing-visits"] });
      // Notice we removed `qc.invalidateQueries({ queryKey: ["invoice"] })` 
      // to prevent the background refetch from overwriting our new data with an empty array.
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

  function onPayment(e: React.FormEvent<HTMLFormElement>) {
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
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <h1 className="text-2xl font-semibold">Reception / Billing</h1>
        
        {zReport.data && (
          <div className="bg-white border rounded-lg px-4 py-3 shadow-sm text-sm">
            <span className="text-slate-500 font-medium">My Shift ({zReport.data.date}): </span>
            <span className="font-bold text-emerald-600 ml-1">ZMW {zReport.data.total_collected}</span>
            <span className="text-xs text-slate-400 ml-2">({zReport.data.summary.length} transactions)</span>
          </div>
        )}
      </div>
      
      <div className="grid md:grid-cols-2 gap-6">
        {/* Visit List */}
        <div className="bg-white border rounded-lg overflow-hidden h-fit">
          <div className="bg-slate-50 px-4 py-2 border-b text-sm font-semibold text-slate-600">Ready for Billing (Closed Visits)</div>
          <ul className="divide-y text-sm">
            {visits.data?.results.map((v: any) => (
              <li key={v.id}>
                <button onClick={() => setSelectedVisit(v.id)} className={`w-full text-left px-4 py-3 hover:bg-slate-50 ${selectedVisit === v.id ? "bg-sky-50" : ""}`}>
                  <p className="font-medium text-slate-800">{v.patient_name}</p>
                  <p className="text-slate-500 text-xs">{v.visit_no} · {new Date(v.closed_at).toLocaleDateString()}</p>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Invoice Panel */}
        <div className="bg-white border rounded-lg p-6">
          {!selectedVisit ? (
            <p className="text-slate-500 text-sm">Select a visit to view or generate the bill.</p>
          ) : invoice.isLoading ? (
            <p className="text-slate-500 text-sm">Checking for invoice…</p>
          ) : !invoice.data ? (
            <div className="text-center py-8">
              <p className="text-slate-500 text-sm mb-4">No invoice generated. Make sure the visit is closed.</p>
              <button onClick={() => generateInvoice.mutate(selectedVisit)} disabled={generateInvoice.isPending} className="bg-slate-200 text-slate-700 px-4 py-2 rounded text-sm hover:bg-slate-300">
                Force Generate
              </button>
            </div>
          ) : (
            <div>
              <div className="flex justify-between items-start border-b pb-4 mb-4">
                <div>
                  <h2 className="font-semibold text-lg">{invoice.data.invoice_no}</h2>
                  <p className="text-slate-500 text-sm">{invoice.data.patient_name}</p>
                </div>
                <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-1 rounded font-medium">{invoice.data.status}</span>
              </div>
              
              <ul className="space-y-2 text-sm mb-4">
                {invoice.data.items.map((i: any) => (
                  <li key={i.id} className="flex justify-between text-slate-600">
                    <span>{i.quantity}x {i.description}</span>
                    <span>ZMW {i.total}</span>
                  </li>
                ))}
              </ul>
              
              <div className="flex justify-between font-bold text-lg border-t pt-2">
                <span>Total</span>
                <span>ZMW {invoice.data.total}</span>
              </div>
              <div className="flex justify-between font-medium text-emerald-600 border-b pb-4 mb-4">
                <span>Balance Due</span>
                <span>ZMW {invoice.data.balance}</span>
              </div>

              <button onClick={() => window.print()} className="w-full mb-4 bg-sky-100 text-sky-700 font-medium py-2 rounded hover:bg-sky-200">
                Print Receipt
              </button>

              {/* Printable Area (Hidden on screen, visible on print) */}
              <div id="print-area" className="hidden">
                <div className="text-center mb-6">
                  <h1 className="text-2xl font-bold">Nimbus OPD Cloud</h1>
                  <p className="text-sm">Official Receipt</p>
                </div>
                <div className="flex justify-between mb-4 text-sm">
                  <div>
                    <p><b>Receipt:</b> {invoice.data.invoice_no}</p>
                    <p><b>Patient:</b> {invoice.data.patient_name}</p>
                  </div>
                  <div className="text-right">
                    <p><b>Date:</b> {new Date().toLocaleDateString()}</p>
                  </div>
                </div>
                <table className="w-full text-sm mb-6">
                  <thead className="border-b">
                    <tr><th className="text-left py-2">Item</th><th className="text-right py-2">Amount</th></tr>
                  </thead>
                  <tbody>
                    {invoice.data.items.map((i: any) => (
                      <tr key={i.id}>
                        <td className="py-2">{i.quantity}x {i.description}</td>
                        <td className="text-right py-2">{i.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="border-t pt-2 text-right">
                  <p className="font-bold text-lg">Total: ZMW {invoice.data.total}</p>
                </div>
                <p className="text-center text-xs mt-12">Thank you for choosing Nimbus OPD.</p>
              </div>

              {invoice.data.balance > 0 && (
                <form onSubmit={onPayment} className="mt-6 border-t pt-4 space-y-3 bg-slate-50 -mx-6 -mb-6 p-6 rounded-b-lg">
                  <h3 className="text-sm font-semibold text-slate-700">Record Payment</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="text-xs">
                      <span className="text-slate-500">Amount</span>
                      <input name="amount" defaultValue={invoice.data.balance} required className="w-full mt-1 border rounded px-2 py-1.5" />
                    </label>
                    <label className="text-xs">
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
                    </label>
                  </div>
                  <label className="text-xs block">
                    <span className="text-slate-500">Reference / Receipt #</span>
                    <input name="reference" className="w-full mt-1 border rounded px-2 py-1.5" />
                  </label>
                  <button type="submit" disabled={recordPayment.isPending} className="w-full bg-emerald-600 text-white py-2 rounded text-sm font-medium hover:bg-emerald-700">
                    {recordPayment.isPending ? "Processing..." : "Complete Payment"}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
