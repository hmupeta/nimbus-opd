import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import type { Paginated, Patient, Visit } from "../api/types";

const PROVINCES = [
  { value: "central", label: "Central" },
  { value: "copperbelt", label: "Copperbelt" },
  { value: "eastern", label: "Eastern" },
  { value: "luapula", label: "Luapula" },
  { value: "lusaka", label: "Lusaka" },
  { value: "muchinga", label: "Muchinga" },
  { value: "northern", label: "Northern" },
  { value: "north_western", label: "North-Western" },
  { value: "southern", label: "Southern" },
  { value: "western", label: "Western" },
];

export default function Patients() {
  const [q, setQ] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formDob, setFormDob] = useState<string>("");
  const nav = useNavigate();
  const qc = useQueryClient();

  const list = useQuery({
    queryKey: ["patients", q],
    queryFn: async () =>
      (await api.get<Paginated<Patient>>("/patients/", {
        params: q ? { q } : undefined,
      })).data,
  });

  const startVisit = useMutation({
    mutationFn: async (patientId: number) => {
      const { data } = await api.post<Visit>("/visits/", {
        patient: patientId, visit_type: "OPD",
      });
      return data;
    },
    onSuccess: (visit) => {
      qc.invalidateQueries({ queryKey: ["visits"] });
      nav(`/visits/${visit.id}`);
    },
  });

  const createPatient = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post<Patient>("/patients/", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      setShowForm(false);
      setFormDob("");
      setFormError(null);
    },
    onError: (err: any) => {
      const data = err.response?.data;
      if (typeof data === "object") {
        const messages = Object.entries(data).map(([k, v]) => `${k}: ${v}`).join("\n");
        setFormError(messages);
      } else {
        setFormError(data?.detail || "Failed to create patient.");
      }
    }
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: any = {};
    fd.forEach((v, k) => {
      if (v !== "") payload[k] = String(v);
    });
    createPatient.mutate(payload);
  }

  // Calculate if the entered DOB makes the patient a minor
  const isMinor = (() => {
    if (!formDob) return false;
    const birth = new Date(formDob);
    const today = new Date();
    let age = today.getFullYear() - birth.getFullYear();
    const m = today.getMonth() - birth.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
    return age < 18;
  })();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Patients</h1>
        <input
          placeholder="Search name, MRN, NRC, phone…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="ml-auto border rounded px-3 py-2 w-72"
        />
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded bg-sky-600 text-white px-3 py-2 hover:bg-sky-700"
        >
          + New patient
        </button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-lg p-6 space-y-6 shadow-sm">
          {formError && (
            <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200 text-sm whitespace-pre-wrap font-mono">
              {formError}
            </div>
          )}
          <div className="flex items-center justify-between border-b pb-4">
            <h2 className="text-lg font-medium">Register New Patient</h2>
            <button type="button" onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-600">✕</button>
          </div>

          {/* Identity */}
          <div>
            <h3 className="text-sm font-semibold text-sky-700 mb-3 uppercase tracking-wide">Identity</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <label className="block text-sm md:col-span-1">
                <span className="text-slate-600">First Name *</span>
                <input name="first_name" required className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm md:col-span-1">
                <span className="text-slate-600">Last Name *</span>
                <input name="last_name" required className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm md:col-span-1">
                <span className="text-slate-600">Date of Birth</span>
                <input type="date" name="dob" value={formDob} onChange={(e) => setFormDob(e.target.value)} className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm md:col-span-1">
                <span className="text-slate-600">Sex</span>
                <select name="sex" className="mt-1 w-full border rounded px-3 py-2">
                  <option value="">Select...</option>
                  <option value="M">Male</option>
                  <option value="F">Female</option>
                  <option value="O">Other</option>
                </select>
              </label>
              <label className="block text-sm md:col-span-2">
                <span className="text-slate-600">National ID (NRC)</span>
                <input name="national_id" placeholder="e.g. 123456/78/1" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm md:col-span-1">
                <span className="text-slate-600">Passport #</span>
                <input name="passport_number" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm md:col-span-1">
                <span className="text-slate-600">NHIMA #</span>
                <input name="nhima_number" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
            </div>
          </div>

          {/* Contact */}
          <div>
            <h3 className="text-sm font-semibold text-sky-700 mb-3 uppercase tracking-wide">Contact</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <label className="block text-sm">
                <span className="text-slate-600">Phone</span>
                <input name="phone" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Alternative Phone</span>
                <input name="alternative_phone" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Email</span>
                <input type="email" name="email" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
            </div>
          </div>

          {/* Address */}
          <div>
            <h3 className="text-sm font-semibold text-sky-700 mb-3 uppercase tracking-wide">Address</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <label className="block text-sm">
                <span className="text-slate-600">Province</span>
                <select name="province" className="mt-1 w-full border rounded px-3 py-2">
                  <option value="">Select...</option>
                  {PROVINCES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">District</span>
                <input name="district" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">City/Town</span>
                <input name="city_town" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm md:col-span-1">
                <span className="text-slate-600">Compound/Village</span>
                <input name="compound_village" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm md:col-span-2">
                <span className="text-slate-600">Street Address</span>
                <input name="street_address" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
            </div>
          </div>

          {/* Guardian (Conditional) */}
          {isMinor && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-amber-800 mb-1 uppercase tracking-wide">Parent / Guardian</h3>
              <p className="text-xs text-amber-700 mb-3">Patient is under 18. Guardian details are required.</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <label className="block text-sm">
                  <span className="text-slate-700">Guardian Name *</span>
                  <input name="guardian_name" required={isMinor} className="mt-1 w-full border rounded px-3 py-2" />
                </label>
                <label className="block text-sm">
                  <span className="text-slate-700">Relationship</span>
                  <input name="guardian_relationship" placeholder="e.g. Mother" className="mt-1 w-full border rounded px-3 py-2" />
                </label>
                <label className="block text-sm">
                  <span className="text-slate-700">Guardian Phone *</span>
                  <input name="guardian_phone" required={isMinor} className="mt-1 w-full border rounded px-3 py-2" />
                </label>
                <label className="block text-sm md:col-span-1">
                  <span className="text-slate-700">Guardian NRC</span>
                  <input name="guardian_nrc" className="mt-1 w-full border rounded px-3 py-2" />
                </label>
                <label className="block text-sm md:col-span-2">
                  <span className="text-slate-700">Guardian Address</span>
                  <input name="guardian_address" className="mt-1 w-full border rounded px-3 py-2" />
                </label>
              </div>
            </div>
          )}

          {/* Clinical & Demographics */}
          <div>
            <h3 className="text-sm font-semibold text-sky-700 mb-3 uppercase tracking-wide">Clinical & Demographics</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <label className="block text-sm">
                <span className="text-slate-600">Marital Status</span>
                <select name="marital_status" className="mt-1 w-full border rounded px-3 py-2">
                  <option value="">Select...</option>
                  <option value="single">Single</option>
                  <option value="married">Married</option>
                  <option value="divorced">Divorced</option>
                  <option value="widowed">Widowed</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Occupation</span>
                <input name="occupation" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Blood Group</span>
                <select name="blood_group" className="mt-1 w-full border rounded px-3 py-2">
                  <option value="">Select...</option>
                  {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(bg => <option key={bg} value={bg}>{bg}</option>)}
                </select>
              </label>
              <label className="block text-sm md:col-span-3">
                <span className="text-slate-600">Allergies</span>
                <input name="allergies" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm md:col-span-3">
                <span className="text-slate-600">Chronic Conditions</span>
                <input name="chronic_conditions" className="mt-1 w-full border rounded px-3 py-2" />
              </label>
            </div>
          </div>

          <div className="pt-2 flex justify-end gap-3">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded border">Cancel</button>
            <button type="submit" disabled={createPatient.isPending} className="px-6 py-2 text-sm font-medium text-white bg-sky-600 hover:bg-sky-700 rounded disabled:opacity-50">
              {createPatient.isPending ? "Saving..." : "Save Patient"}
            </button>
          </div>
        </form>
      )}

      {list.isLoading && <p className="text-slate-500">Loading…</p>}
      {list.data && (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-4 py-2">MRN</th>
                <th className="text-left px-4 py-2">Name</th>
                <th className="text-left px-4 py-2">Sex</th>
                <th className="text-left px-4 py-2">Phone</th>
                <th className="text-left px-4 py-2">NRC / Passport</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y">
              {list.data.results.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs">{p.mrn}</td>
                  <td className="px-4 py-3">
                    <Link to={`/patients/${p.id}`} className="font-medium text-sky-700 hover:underline">
                      {p.full_name}
                    </Link>
                    {p.is_minor && <span className="ml-2 text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">Minor</span>}
                  </td>
                  <td className="px-4 py-3">{p.sex}</td>
                  <td className="px-4 py-3">{p.phone}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {p.national_id || p.passport_number || "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => startVisit.mutate(p.id)}
                      disabled={startVisit.isPending}
                      className="rounded bg-emerald-600 text-white text-xs px-3 py-1.5 hover:bg-emerald-700 disabled:opacity-50"
                    >
                      Start visit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.data.results.length === 0 && (
            <p className="p-4 text-slate-500 text-center">No patients found.</p>
          )}
        </div>
      )}
    </div>
  );
}
