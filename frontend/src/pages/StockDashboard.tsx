import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function StockDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["stock"],
    queryFn: async () => (await api.get<Paginated<any>>("/stock/")).data.results,
  });

  const isExpiring = (dateStr: string) => {
    const expiry = new Date(dateStr).getTime();
    const today = new Date().getTime();
    const days90 = 90 * 24 * 60 * 60 * 1000;
    return expiry - today < days90;
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Inventory & Stock Levels</h1>
      <p className="text-sm text-slate-500">Monitor batches and expiry dates. <span className="text-red-500 font-medium">Red</span> indicates low stock or near expiry.</p>

      {isLoading && <p className="text-slate-500">Loading...</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Medicine</th>
              <th className="text-left px-4 py-3">Batch No</th>
              <th className="text-left px-4 py-3">Expiry Date</th>
              <th className="text-left px-4 py-3">Qty Available</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.map((s: any) => {
              const lowStock = s.quantity < 50;
              const expiring = isExpiring(s.expiry_date);
              return (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{s.medicine_name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{s.batch_no}</td>
                  <td className={`px-4 py-3 ${expiring ? "text-red-600 font-bold" : ""}`}>{s.expiry_date}</td>
                  <td className={`px-4 py-3 font-bold ${lowStock ? "text-red-600" : "text-slate-700"}`}>{s.quantity}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {data?.length === 0 && <p className="p-6 text-center text-slate-500">No stock records found.</p>}
      </div>
    </div>
  );
}
