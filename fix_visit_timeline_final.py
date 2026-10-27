#!/usr/bin/env python3
"""
fix_visit_timeline_final.py -- Complete overwrite of VisitTimeline.tsx to show order details.
"""
from pathlib import Path

FRONTEND = Path.cwd() / "frontend"
vp = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"

content = '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { currentUser } from "../api/auth";
import type { Timeline, Paginated } from "../api/types";

export default function VisitTimeline() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const user = currentUser();
  
  const [showVitalsForm, setShowVitalsForm] = useState(false);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [showLabForm, setShowLabForm] = useState(false);
  const [showRadForm, setShowRadForm] = useState(false);
  const [showMedForm, setShowMedForm] = useState(false);

  const isNurse = user?.role === "nurse";
  const isDoctor = user?.role === "doctor";
  const isAdmin = user?.role === "admin";

  const canRecordVitals = isNurse || isAdmin || isDoctor;
  const canAddNote = isDoctor || isAdmin;
  const canOrder = isDoctor || isAdmin;

  const q = useQuery({
    queryKey: ["visit", id, "timeline"],
    queryFn: async () => (await api.get<Timeline>(`/visits/${id}/timeline/`)).data,
    enabled: !!id,
  });

  const labs = useQuery({
    queryKey: ["lab-tests"],
    queryFn: async () => (await api.get<Paginated<any>>("/lab-tests/")).data.results,
  });

  const meds = useQuery({
    queryKey: ["medicines"],
    queryFn: async () => (await api.get<Paginated<any>>("/medicines/")).data.results,
  });

  const closeVisit = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/visits/${id}/close/`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] }),
    onError: (error: any) => {
      const msg = error.response?.data?.detail || "Failed to close visit.";
      alert(`Cannot Close Visit:\\n\\n${msg}`);
    }
  });

  const recordVitals = useMutation({
    mutationFn: async (payload: any) => {
      await api.post(`/visits/${id}/record_vitals/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowVitalsForm(false);
    },
  });

  const addNote = useMutation({
    mutationFn: async (payload: any) => {
      await api.post(`/notes/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowNoteForm(false);
    },
  });

  const orderLab = useMutation({
    mutationFn: async (testId: number) => {
      await api.post(`/visits/${id}/order_lab/`, { test: testId });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowLabForm(false);
    },
  });

  const orderRadiology = useMutation({
    mutationFn: async (payload: any) => {
      await api.post(`/visits/${id}/order_radiology/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowRadForm(false);
    },
  });

  const prescribe = useMutation({
    mutationFn: async (payload: any) => {
      await api.post(`/visits/${id}/prescribe/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowMedForm(false);
    },
  });

  function onVitalsSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: any = {};
    fd.forEach((v, k) => { if (v !== "") payload[k] = String(v); });
    recordVitals.mutate(payload);
  }

  function onNoteSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    addNote.mutate({
      visit: Number(id),
      kind: "soap",
      subjective: String(fd.get("subjective") || ""),
      objective: String(fd.get("objective") || ""),
      assessment: String(fd.get("assessment") || ""),
      plan: String(fd.get("plan") || ""),
    });
  }

  if (q.isLoading) return <p className="text-slate-500">Loading…</p>;
  if (q.error || !q.data) return <p className="text-red-600">Failed to load.</p>;

  const t = q.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/" className="text-sm text-sky-700">← Dashboard</Link>
        <h1 className="text-2xl font-semibold">
          {t.visit_no} — {t.patient.full_name}
        </h1>
        <span className="text-xs bg-sky-100 text-sky-700 rounded px-2 py-0.5">
          {t.status}
        </span>
        {t.status !== "closed" && (
          <button onClick={() => closeVisit.mutate()}
            disabled={closeVisit.isPending}
            className="ml-auto rounded bg-slate-700 text-white text-sm px-3 py-1.5 hover:bg-slate-800 disabled:opacity-50">
            Close visit
          </button>
        )}
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <Card title="Patient">
          <p className="font-medium">{t.patient.full_name}</p>
          <p className="text-sm text-slate-500">MRN {t.patient.mrn}</p>
          <p className="text-sm text-slate-500">{t.patient.phone}</p>
        </Card>

        {/* VITALS */}
        <Card title="Vitals">
          {t.vitals && !showVitalsForm ? (
            <div className="space-y-2">
              <ul className="text-sm space-y-1">
                <li><span className="text-slate-500 w-16 inline-block">Temp:</span> {t.vitals.temperature_c}°C</li>
                <li><span className="text-slate-500 w-16 inline-block">BP:</span> {t.vitals.systolic}/{t.vitals.diastolic}</li>
                <li><span className="text-slate-500 w-16 inline-block">Pulse:</span> {t.vitals.pulse}</li>
                <li><span className="text-slate-500 w-16 inline-block">SpO₂:</span> {t.vitals.spo2}%</li>
              </ul>
              {canRecordVitals && t.status !== "closed" && (
                <button onClick={() => setShowVitalsForm(true)} className="text-xs text-sky-600 hover:underline mt-2">
                  Update Vitals
                </button>
              )}
            </div>
          ) : showVitalsForm ? (
            <form onSubmit={onVitalsSubmit} className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <label className="text-xs"><span className="text-slate-500">Temp (°C)</span><input type="number" step="0.1" name="temperature_c" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">SpO₂ (%)</span><input type="number" name="spo2" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Systolic</span><input type="number" name="systolic" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Diastolic</span><input type="number" name="diastolic" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Pulse</span><input type="number" name="pulse" className="w-full border rounded px-2 py-1 mt-1" /></label>
                <label className="text-xs"><span className="text-slate-500">Weight (kg)</span><input type="number" step="0.1" name="weight_kg" className="w-full border rounded px-2 py-1 mt-1" /></label>
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button type="button" onClick={() => setShowVitalsForm(false)} className="text-xs text-slate-500 hover:text-slate-700">Cancel</button>
                <button type="submit" disabled={recordVitals.isPending} className="text-xs bg-sky-600 text-white px-3 py-1 rounded hover:bg-sky-700 disabled:opacity-50">Save</button>
              </div>
            </form>
          ) : (
            <div>
              <p className="text-sm text-slate-500 mb-2">Not recorded</p>
              {canRecordVitals && t.status !== "closed" && (
                <button onClick={() => setShowVitalsForm(true)} className="text-xs bg-sky-100 text-sky-700 px-2 py-1 rounded hover:bg-sky-200">+ Record Vitals</button>
              )}
            </div>
          )}
        </Card>

        {/* ORDERS */}
        <Card title="Orders">
          <ul className="text-sm space-y-2 mb-2">
            {t.orders.map((o) => (
              <li key={o.id} className="flex flex-col py-1 border-b last:border-0">
                <div className="flex justify-between items-center mb-1">
                  <span className="capitalize font-medium text-slate-700">{o.kind}</span>
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${o.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {o.status}
                  </span>
                </div>
                <ul className="text-xs text-slate-500 pl-2 border-l-2 border-slate-100">
                  {o.items.map(i => (
                    <li key={i.id}>{i.quantity}x {i.description} ({i.code})</li>
                  ))}
                </ul>
              </li>
            ))}
            {t.orders.length === 0 && <li className="text-slate-500">None</li>}
          </ul>

          {canOrder && t.status !== "closed" && (
            <div className="mt-3 pt-3 border-t space-y-2">
              {!showLabForm && !showMedForm && !showRadForm && (
                <div className="flex gap-2">
                  <button onClick={() => setShowLabForm(true)} className="flex-1 text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 py-1.5 rounded hover:bg-indigo-100 font-medium">+ Lab</button>
                  <button onClick={() => setShowRadForm(true)} className="flex-1 text-xs bg-orange-50 text-orange-700 border border-orange-200 py-1.5 rounded hover:bg-orange-100 font-medium">+ Rad</button>
                  <button onClick={() => setShowMedForm(true)} className="flex-1 text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 py-1.5 rounded hover:bg-emerald-100 font-medium">+ Rx</button>
                </div>
              )}

              {showLabForm && (
                <form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); orderLab.mutate(Number(fd.get("test"))); }} className="space-y-2 bg-indigo-50 p-2 rounded border border-indigo-100">
                  <select name="test" required className="w-full border rounded px-2 py-1 text-xs">
                    <option value="">Select Lab Test...</option>
                    {labs.data?.map((l: any) => <option key={l.id} value={l.id}>{l.name} ({l.code})</option>)}
                  </select>
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setShowLabForm(false)} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={orderLab.isPending} className="text-[10px] bg-indigo-600 text-white px-2 py-1 rounded">Order</button>
                  </div>
                </form>
              )}

              {showRadForm && (
                <form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); orderRadiology.mutate({ modality: fd.get("modality"), body_part: fd.get("body_part"), notes: fd.get("notes") }); }} className="space-y-2 bg-orange-50 p-2 rounded border border-orange-100">
                  <div className="grid grid-cols-2 gap-1">
                    <select name="modality" required className="w-full border rounded px-2 py-1 text-xs">
                      <option value="X-ray">X-ray</option>
                      <option value="CT">CT</option>
                      <option value="MRI">MRI</option>
                      <option value="US">Ultrasound</option>
                    </select>
                    <input name="body_part" placeholder="Body Part (e.g. Chest)" required className="w-full border rounded px-2 py-1 text-xs" />
                  </div>
                  <input name="notes" placeholder="Clinical notes..." className="w-full border rounded px-2 py-1 text-xs" />
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setShowRadForm(false)} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={orderRadiology.isPending} className="text-[10px] bg-orange-600 text-white px-2 py-1 rounded">Order</button>
                  </div>
                </form>
              )}

              {showMedForm && (
                <form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); prescribe.mutate({ medicine: Number(fd.get("medicine")), dose: fd.get("dose"), frequency: fd.get("frequency"), duration_days: Number(fd.get("duration_days")), quantity: Number(fd.get("quantity")) }); }} className="space-y-2 bg-emerald-50 p-2 rounded border border-emerald-100">
                  <select name="medicine" required className="w-full border rounded px-2 py-1 text-xs">
                    <option value="">Select Medication...</option>
                    {meds.data?.map((m: any) => <option key={m.id} value={m.id}>{m.name} {m.strength}</option>)}
                  </select>
                  <div className="grid grid-cols-2 gap-1">
                    <input name="dose" defaultValue="1 tab" placeholder="Dose" required className="w-full border rounded px-1 py-1 text-xs" />
                    <input name="frequency" defaultValue="TID" placeholder="Freq" required className="w-full border rounded px-1 py-1 text-xs" />
                    <input type="number" name="duration_days" defaultValue="3" placeholder="Days" required className="w-full border rounded px-1 py-1 text-xs" />
                    <input type="number" name="quantity" defaultValue="9" placeholder="Qty" required className="w-full border rounded px-1 py-1 text-xs" />
                  </div>
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setShowMedForm(false)} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={prescribe.isPending} className="text-[10px] bg-emerald-600 text-white px-2 py-1 rounded">Prescribe</button>
                  </div>
                </form>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* CLINICAL NOTES */}
      <div className="bg-white border rounded-lg p-4">
        <div className="flex justify-between items-center mb-4 border-b pb-2">
          <h2 className="text-sm font-semibold text-slate-600">Clinical notes</h2>
          {canAddNote && !showNoteForm && t.status !== "closed" && (
            <button onClick={() => setShowNoteForm(true)} className="text-xs bg-sky-100 text-sky-700 px-2 py-1 rounded hover:bg-sky-200 font-medium">
              + Add SOAP Note
            </button>
          )}
        </div>
        
        {showNoteForm && (
          <form onSubmit={onNoteSubmit} className="mb-6 bg-slate-50 border rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-sky-800">New SOAP Note</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <label className="block text-xs"><span className="text-slate-600 font-medium">Subjective</span><textarea name="subjective" rows={2} className="mt-1 w-full border rounded px-2 py-1" /></label>
              <label className="block text-xs"><span className="text-slate-600 font-medium">Objective</span><textarea name="objective" rows={2} className="mt-1 w-full border rounded px-2 py-1" /></label>
              <label className="block text-xs"><span className="text-slate-600 font-medium">Assessment</span><textarea name="assessment" rows={2} className="mt-1 w-full border rounded px-2 py-1" /></label>
              <label className="block text-xs"><span className="text-slate-600 font-medium">Plan</span><textarea name="plan" rows={2} className="mt-1 w-full border rounded px-2 py-1" /></label>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowNoteForm(false)} className="text-xs text-slate-500 hover:text-slate-700">Cancel</button>
              <button type="submit" disabled={addNote.isPending} className="text-xs bg-sky-600 text-white px-4 py-1.5 rounded hover:bg-sky-700">Save Note</button>
            </div>
          </form>
        )}

        {t.notes.length === 0 && !showNoteForm ? (
          <p className="text-sm text-slate-500">No notes yet.</p>
        ) : (
          <ul className="space-y-4">
            {t.notes.map((n) => (
              <li key={n.id} className="text-sm border-l-2 border-sky-200 pl-3 py-1">
                <p className="font-medium text-slate-700">{n.kind.toUpperCase()} — {new Date(n.created_at).toLocaleString()}</p>
                <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-slate-700">
                  <p><span className="text-slate-500 font-medium mr-1">S:</span> {n.subjective}</p>
                  <p><span className="text-slate-500 font-medium mr-1">O:</span> {n.objective}</p>
                  <p><span className="text-slate-500 font-medium mr-1">A:</span> {n.assessment}</p>
                  <p><span className="text-slate-500 font-medium mr-1">P:</span> {n.plan}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Card title="Radiology orders">
        {(t.rad_orders as any[]).length === 0 ? (
          <p className="text-sm text-slate-500">No radiology orders.</p>
        ) : (
          <ul className="text-sm space-y-3">
            {(t.rad_orders as any[]).map((o) => (
              <li key={o.id} className="flex justify-between items-start py-2 border-b last:border-0">
                <div className="w-full">
                  <div className="flex justify-between items-center w-full mb-1">
                    <span className="font-medium text-slate-700">{o.modality} - {o.body_part}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${o.status === 'reported' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                      {o.status}
                    </span>
                  </div>
                  {o.status === "reported" && (
                    <div className="mt-2 text-xs text-slate-600 bg-slate-50 p-2 rounded border">
                      <p><b>Findings:</b> {o.findings}</p>
                      <p><b>Impression:</b> {o.impression}</p>
                      {o.image && (
                        <a href={o.image} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sky-600 hover:underline font-medium">
                          View Attached Image ↗
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Pharmacy orders">
        {(t.pharm_orders as any[]).length === 0 ? (
          <p className="text-sm text-slate-500">No prescriptions.</p>
        ) : (
          <ul className="text-sm space-y-3">
            {(t.pharm_orders as any[]).map((o) => (
              <li key={o.id} className="flex justify-between items-start py-2 border-b last:border-0">
                <div className="w-full">
                  <div className="flex justify-between items-center w-full mb-1">
                    <span className="text-xs font-semibold text-slate-500 uppercase">Prescription</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${o.status === 'dispensed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                      {o.status}
                    </span>
                  </div>
                  <ul className="space-y-1 bg-slate-50 p-2 rounded border">
                    {o.items.map((i: any) => (
                      <li key={i.id} className="flex justify-between text-xs">
                        <span><b>{i.medicine_name}</b> ({i.dose} {i.frequency})</span>
                        <span className={i.quantity_dispensed > 0 ? "text-emerald-600 font-medium" : "text-slate-500"}>
                          {i.quantity_dispensed > 0 ? `Dispensed: ${i.quantity_dispensed}` : `Pending: ${i.quantity_prescribed}`}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Lab orders">
        {t.lab_orders.length === 0 ? (
          <p className="text-sm text-slate-500">No lab orders.</p>
        ) : (
          <ul className="text-sm space-y-2">
            {t.lab_orders.map((l) => (
              <li key={l.id} className="flex justify-between items-start py-2 border-b last:border-0">
                <div>
                  <span className="font-medium text-slate-700">{l.test_name}</span>
                  <span className="ml-2 text-xs text-slate-400 font-mono">{l.test_code}</span>
                  {l.result && (
                    <div className="mt-1 text-xs text-slate-600 bg-slate-50 p-2 rounded border">
                      <p>Result: <b>{l.result.value_text} {l.result.unit}</b></p>
                      <p>Flag: <b className={l.result.flag !== "normal" ? "text-red-600" : "text-emerald-600"}>{l.result.flag.toUpperCase()}</b></p>
                      {l.result.comment && <p>Comment: {l.result.comment}</p>}
                    </div>
                  )}
                </div>
                <span className="text-[10px] font-medium text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded ml-2">{l.status}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <h2 className="text-sm font-semibold text-slate-600 mb-2 border-b pb-1">{title}</h2>
      {children}
    </div>
  );
}
'''

vp.write_text(content, encoding="utf-8")
print("   overwrote VisitTimeline.tsx")