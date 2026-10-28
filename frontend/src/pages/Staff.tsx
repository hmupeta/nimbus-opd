import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

const ROLES = [
  { value: "doctor", label: "Doctor" },
  { value: "nurse", label: "Nurse" },
  { value: "receptionist", label: "Receptionist" },
  { value: "lab", label: "Lab Technician" },
  { value: "radiology", label: "Radiologist" },
  { value: "pharmacist", label: "Pharmacist" },
];

export default function Staff() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const staff = useQuery({
    queryKey: ["staff"],
    queryFn: async () => (await api.get<Paginated<any>>("/users/")).data.results,
  });

  const createStaff = useMutation({
    mutationFn: async (payload: any) => {
      await api.post("/users/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["staff"] });
      setShowForm(false);
    },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createStaff.mutate({
      email: fd.get("email"),
      first_name: fd.get("first_name"),
      last_name: fd.get("last_name"),
      role: fd.get("role"),
      password: fd.get("password"),
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Staff Management</h1>
          <p className="text-sm text-slate-500 mt-1">Create and manage user accounts for your clinic.</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium">
          + Add Staff Member
        </button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="block text-sm">
              <span className="text-slate-600 font-medium">First Name</span>
              <input name="first_name" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-600 font-medium">Last Name</span>
              <input name="last_name" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-600 font-medium">Email Address</span>
              <input type="email" name="email" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-600 font-medium">Role</span>
              <select name="role" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="">Select a role...</option>
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </label>
            <label className="block text-sm col-span-2">
              <span className="text-slate-600 font-medium">Temporary Password</span>
              <input type="password" name="password" required minLength={6} className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-slate-600 border rounded-lg hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={createStaff.isPending} className="px-4 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-700">
              {createStaff.isPending ? "Creating..." : "Create Account"}
            </button>
          </div>
        </form>
      )}

      {staff.isLoading && <p className="text-slate-500">Loading staff list...</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Email</th>
              <th className="text-left px-4 py-3">Role</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {staff.data?.map((u: any) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{u.first_name} {u.last_name}</td>
                <td className="px-4 py-3 text-slate-500">{u.email}</td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-slate-100 px-2 py-1 rounded capitalize">{u.role}</span>
                </td>
                <td className="px-4 py-3">
                  {u.is_active ? <span className="text-emerald-600 font-medium">Active</span> : <span className="text-red-500 font-medium">Inactive</span>}
                </td>
              </tr>
            ))}
            {staff.data?.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">No staff members found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
