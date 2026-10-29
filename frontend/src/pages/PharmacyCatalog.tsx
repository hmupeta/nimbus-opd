import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PharmacyCatalog() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const meds = useQuery({
    queryKey: ["medicines"],
    queryFn: async () => (await api.get<Paginated<any>>("/medicines/")).data.results,
  });

  const createMed = useMutation({
    mutationFn: async (payload: any) => await api.post("/medicines/", payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medicines"] }); setShowForm(false); },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createMed.mutate({
      code: fd.get("code"), name: fd.get("name"), form: fd.get("form"), strength: fd.get("strength"),
      base_price: Number(fd.get("price")), is_active: true,
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-800">Pharmacy Catalog</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700">+ Add Medicine</button>
      </div>
      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm"><span>Code</span><input name="code" required placeholder="e.g. PARA500" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Name</span><input name="name" required placeholder="Paracetamol" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Form</span><input name="form" placeholder="Tablet" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Strength</span><input name="strength" placeholder="500 mg" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Price (ZMW)</span><input type="number" step="0.01" name="price" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
          </div>
          <button type="submit" className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700">Save</button>
        </form>
      )}
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr><th className="text-left px-4 py-3">Code</th><th className="text-left px-4 py-3">Name</th><th className="text-left px-4 py-3">Form</th><th className="text-left px-4 py-3">Price</th></tr></thead>
          <tbody className="divide-y">
            {meds.data?.map((m: any) => (
              <tr key={m.id}><td className="px-4 py-3 font-mono">{m.code}</td><td className="px-4 py-3">{m.name}</td><td className="px-4 py-3">{m.form} {m.strength}</td><td className="px-4 py-3">ZMW {m.base_price}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
