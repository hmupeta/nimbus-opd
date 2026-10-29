import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function LabCatalog() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const tests = useQuery({
    queryKey: ["lab-tests"],
    queryFn: async () => (await api.get<Paginated<any>>("/lab-tests/")).data.results,
  });

  const createTest = useMutation({
    mutationFn: async (payload: any) => await api.post("/lab-tests/", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lab-tests"] });
      setShowForm(false);
    },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createTest.mutate({
      code: fd.get("code"),
      name: fd.get("name"),
      base_price: Number(fd.get("price")),
      specimen_type: fd.get("specimen"),
      is_active: true,
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Lab Test Catalog</h1>
          <p className="text-sm text-slate-500 mt-1">Manage the tests available in the Doctor's dropdown.</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium">
          + Add Lab Test
        </button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm"><span className="text-slate-600">Test Code</span><input name="code" required placeholder="e.g. MAL" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span className="text-slate-600">Test Name</span><input name="name" required placeholder="e.g. Malaria RDT" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span className="text-slate-600">Price (ZMW)</span><input type="number" step="0.01" name="price" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span className="text-slate-600">Specimen</span><input name="specimen" placeholder="e.g. blood" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 border rounded-lg hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={createTest.isPending} className="px-4 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-700">Save Test</button>
          </div>
        </form>
      )}

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Code</th>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Price</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {tests.data?.map((t: any) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono">{t.code}</td>
                <td className="px-4 py-3 font-medium">{t.name}</td>
                <td className="px-4 py-3">ZMW {t.base_price}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-1 rounded ${t.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
            {tests.data?.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">No lab tests configured yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
