#!/usr/bin/env python3
"""
update_frontend_patients.py -- update React frontend to support detailed patient profiles.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path.cwd()
if not (BACKEND / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = BACKEND / "frontend"
if not FRONTEND.exists():
    sys.exit(f"Frontend not found at {FRONTEND}. Run create_frontend.py first.")

def write(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. Update types ───────────────────────────────────────────────────
print("==> Updating types")
write("src/api/types.ts", '''\
export interface Patient {
  id: number;
  mrn: string;
  first_name: string;
  last_name: string;
  full_name: string;
  dob: string | null;
  sex: string;
  age: number | null;
  is_minor: boolean;
  national_id: string;
  passport_number: string;
  nhima_number: string;
  phone: string;
  alternative_phone: string;
  email: string;
  address: string;
  province: string;
  district: string;
  city_town: string;
  compound_village: string;
  street_address: string;
  postal_code: string;
  guardian_name: string;
  guardian_relationship: string;
  guardian_phone: string;
  guardian_nrc: string;
  guardian_address: string;
  marital_status: string;
  occupation: string;
  blood_group: string;
  allergies: string;
  chronic_conditions: string;
  created_at: string;
}

export interface Visit {
  id: number;
  visit_no: string;
  patient: number;
  patient_name: string;
  visit_type: string;
  status: string;
  arrived_at: string;
  closed_at: string | null;
  attending_doctor: number | null;
}

export interface Vitals {
  id: number;
  temperature_c: string | null;
  weight_kg: string | null;
  systolic: number | null;
  diastolic: number | null;
  pulse: number | null;
  spo2: number | null;
  recorded_at: string;
}

export interface ClinicalNote {
  id: number;
  kind: string;
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  created_at: string;
}

export interface Order {
  id: number;
  kind: string;
  status: string;
  priority: string;
  notes: string;
  created_at: string;
  items: { id: number; code: string; description: string; quantity: number }[];
}

export interface LabOrder {
  id: number;
  test: number;
  status: string;
  ordered_at: string;
}

export interface Timeline {
  id: number;
  visit_no: string;
  visit_type: string;
  status: string;
  arrived_at: string;
  closed_at: string | null;
  patient: Patient;
  vitals: Vitals | null;
  notes: ClinicalNote[];
  orders: Order[];
  lab_orders: LabOrder[];
  rad_orders: unknown[];
  pharm_orders: unknown[];
}

export interface DashboardSummary {
  date: string;
  census: {
    total: number;
    waiting: number;
    triaged: number;
    in_consultation: number;
    closed: number;
  };
  revenue: { today: string; this_month: string };
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
''')

# ─── 2. Create PatientDetail.tsx ───────────────────────────────────────
print("==> Creating PatientDetail page")
write("src/pages/PatientDetail.tsx", '''\
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Patient } from "../api/types";

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: p, isLoading } = useQuery({
    queryKey: ["patient", id],
    queryFn: async () => (await api.get<Patient>(`/patients/${id}/`)).data,
    enabled: !!id,
  });

  if (isLoading) return <p className="text-slate-500">Loading…</p>;
  if (!p) return <p className="text-red-600">Patient not found.</p>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link to="/patients" className="text-sm text-sky-700">← Patients</Link>
        <h1 className="text-2xl font-semibold">{p.full_name}</h1>
        <span className="text-xs bg-slate-100 px-2 py-0.5 rounded font-mono">{p.mrn}</span>
        {p.is_minor && <span className="text-xs bg-amber-100 text-amber-700 rounded px-2 py-0.5">Minor</span>}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card title="Identity">
          <Row label="Sex" value={p.sex} />
          <Row label="DOB" value={p.dob || "—"} />
          <Row label="Age" value={p.age !== null ? String(p.age) : "—"} />
          <Row label="National ID (NRC)" value={p.national_id || "—"} />
          <Row label="Passport" value={p.passport_number || "—"} />
          <Row label="NHIMA #" value={p.nhima_number || "—"} />
        </Card>

        <Card title="Contact">
          <Row label="Phone" value={p.phone || "—"} />
          <Row label="Alt Phone" value={p.alternative_phone || "—"} />
          <Row label="Email" value={p.email || "—"} />
        </Card>

        <Card title="Address">
          <Row label="Province" value={p.province || "—"} />
          <Row label="District" value={p.district || "—"} />
          <Row label="City/Town" value={p.city_town || "—"} />
          <Row label="Compound/Village" value={p.compound_village || "—"} />
          <Row label="Street" value={p.street_address || "—"} />
          {p.address && <Row label="Notes" value={p.address} />}
        </Card>

        <Card title="Demographics">
          <Row label="Marital Status" value={p.marital_status || "—"} />
          <Row label="Occupation" value={p.occupation || "—"} />
        </Card>

        {p.is_minor && (
          <Card title="Parent / Guardian" className="md:col-span-2 bg-amber-50/50">
            <Row label="Name" value={p.guardian_name} />
            <Row label="Relationship" value={p.guardian_relationship} />
            <Row label="Phone" value={p.guardian_phone} />
            <Row label="NRC" value={p.guardian_nrc || "—"} />
            <Row label="Address" value={p.guardian_address || "—"} />
          </Card>
        )}

        <Card title="Clinical Snapshot" className="md:col-span-2">
          <Row label="Blood Group" value={p.blood_group || "—"} />
          <Row label="Allergies" value={p.allergies || "None known"} />
          <Row label="Chronic Conditions" value={p.chronic_conditions || "None"} />
        </Card>
      </div>
    </div>
  );
}

function Card({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white border rounded-lg p-5 ${className}`}>
      <h2 className="text-sm font-semibold text-slate-800 mb-4 border-b pb-2">{title}</h2>
      <dl className="space-y-2 text-sm">{children}</dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="col-span-2 font-medium">{value}</dd>
    </div>
  );
}
''')

# ─── 3. Overwrite Patients.tsx with full form ──────────────────────────
print("==> Rewriting Patients page with rich form")
write("src/pages/Patients.tsx", '''\
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
    },
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
''')

# ─── 4. Update Router ──────────────────────────────────────────────────
print("==> Updating Router")
write("src/App.tsx", '''\
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Patients from "./pages/Patients";
import PatientDetail from "./pages/PatientDetail";
import VisitTimeline from "./pages/VisitTimeline";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
          <Route path="/visits/:id" element={<VisitTimeline />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
''')

print("==> Done.")