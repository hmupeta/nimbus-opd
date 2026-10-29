import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function RadiologyCatalog() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const exams = useQuery({
    queryKey: ["radiology-exams"],
    queryFn: async () => (await api.get<Paginated<any>>("/radiology-exams/")).data.results,
  });

  const createExam = useMutation({
    mutationFn: async (payload: any) => await api.post("/radiology-exams/", payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["radiology-exams"] }); setShowForm(false); },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createExam.mutate({
      code: fd.get("code"), name: fd.get("name"), modality: fd.get("modality"),
      body_part: fd.get("body_part"), base_price: Number(fd.get("price")), is_active: true,
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-800">Radiology Catalog</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700">+ Add Exam</button>
      </div>
      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm"><span>Code</span><input name="code" required placeholder="e.g. CXR-PA" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Name</span><input name="name" required placeholder="Chest X-Ray PA" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Modality</span>
              <select name="modality" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="X-ray">X-ray</option><option value="CT">CT</option><option value="MRI">MRI</option><option value="US">Ultrasound</option>
              </select>
            </label>
            <label className="text-sm"><span>Body Part</span><input name="body_part" required placeholder="Chest" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Price (ZMW)</span><input type="number" step="0.01" name="price" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
          </div>
          <button type="submit" className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700">Save</button>
        </form>
      )}
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr><th className="text-left px-4 py-3">Code</th><th className="text-left px-4 py-3">Name</th><th className="text-left px-4 py-3">Modality</th><th className="text-left px-4 py-3">Price</th></tr></thead>
          <tbody className="divide-y">
            {exams.data?.map((e: any) => (
              <tr key={e.id}><td className="px-4 py-3 font-mono">{e.code}</td><td className="px-4 py-3">{e.name}</td><td className="px-4 py-3">{e.modality} ({e.body_part})</td><td className="px-4 py-3">ZMW {e.base_price}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
