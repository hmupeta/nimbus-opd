#!/usr/bin/env python3
"""
add_vitals_ui.py -- Add a Vitals recording form to the Visit Timeline in React.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
if not FRONTEND.exists():
    sys.exit(f"Frontend not found at {FRONTEND}.")


def write(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")


write("src/pages/VisitTimeline.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { currentUser } from "../api/auth";
import type { Timeline } from "../api/types";

export default function VisitTimeline() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const user = currentUser();
  const [showVitalsForm, setShowVitalsForm] = useState(false);

  // Roles allowed to record vitals
  const canRecordVitals = user?.role === "nurse" || user?.role === "admin" || user?.role === "doctor";

  const q = useQuery({
    queryKey: ["visit", id, "timeline"],
    queryFn: async () => (await api.get<Timeline>(`/visits/${id}/timeline/`)).data,
    enabled: !!id,
  });

  const closeVisit = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/visits/${id}/close/`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] }),
  });

  const recordVitals = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post(`/visits/${id}/record_vitals/`, payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowVitalsForm(false);
    },
  });

  function onVitalsSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: any = {};
    fd.forEach((v, k) => {
      if (v !== "") payload[k] = String(v);
    });
    recordVitals.mutate(payload);
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
                <label className="text-xs">
                  <span className="text-slate-500">Temp (°C)</span>
                  <input type="number" step="0.1" name="temperature_c" className="w-full border rounded px-2 py-1 mt-1" />
                </label>
                <label className="text-xs">
                  <span className="text-slate-500">SpO₂ (%)</span>
                  <input type="number" name="spo2" className="w-full border rounded px-2 py-1 mt-1" />
                </label>
                <label className="text-xs">
                  <span className="text-slate-500">Systolic</span>
                  <input type="number" name="systolic" className="w-full border rounded px-2 py-1 mt-1" />
                </label>
                <label className="text-xs">
                  <span className="text-slate-500">Diastolic</span>
                  <input type="number" name="diastolic" className="w-full border rounded px-2 py-1 mt-1" />
                </label>
                <label className="text-xs">
                  <span className="text-slate-500">Pulse</span>
                  <input type="number" name="pulse" className="w-full border rounded px-2 py-1 mt-1" />
                </label>
                <label className="text-xs">
                  <span className="text-slate-500">Weight (kg)</span>
                  <input type="number" step="0.1" name="weight_kg" className="w-full border rounded px-2 py-1 mt-1" />
                </label>
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button type="button" onClick={() => setShowVitalsForm(false)} className="text-xs text-slate-500 hover:text-slate-700">Cancel</button>
                <button type="submit" disabled={recordVitals.isPending} className="text-xs bg-sky-600 text-white px-3 py-1 rounded hover:bg-sky-700 disabled:opacity-50">
                  {recordVitals.isPending ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          ) : (
            <div>
              <p className="text-sm text-slate-500 mb-2">Not recorded</p>
              {canRecordVitals && t.status !== "closed" && (
                <button onClick={() => setShowVitalsForm(true)} className="text-xs bg-sky-100 text-sky-700 px-2 py-1 rounded hover:bg-sky-200">
                  + Record Vitals
                </button>
              )}
            </div>
          )}
        </Card>

        <Card title="Orders">
          <ul className="text-sm space-y-1">
            {t.orders.map((o) => (
              <li key={o.id} className="flex justify-between">
                <span>{o.kind}</span>
                <span className="text-slate-500">{o.status}</span>
              </li>
            ))}
            {t.orders.length === 0 && <li className="text-slate-500">None</li>}
          </ul>
        </Card>
      </div>

      <Card title="Clinical notes">
        {t.notes.length === 0 ? (
          <p className="text-sm text-slate-500">No notes yet.</p>
        ) : (
          <ul className="space-y-3">
            {t.notes.map((n) => (
              <li key={n.id} className="text-sm border-l-2 border-sky-200 pl-3 py-1">
                <p className="font-medium text-slate-700">
                  {n.kind.toUpperCase()} — {new Date(n.created_at).toLocaleString()}
                </p>
                <p className="mt-1"><span className="text-slate-500 font-medium mr-1">S:</span> {n.subjective}</p>
                <p><span className="text-slate-500 font-medium mr-1">O:</span> {n.objective}</p>
                <p><span className="text-slate-500 font-medium mr-1">A:</span> {n.assessment}</p>
                <p><span className="text-slate-500 font-medium mr-1">P:</span> {n.plan}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Lab orders">
        {t.lab_orders.length === 0 ? (
          <p className="text-sm text-slate-500">No lab orders.</p>
        ) : (
          <ul className="text-sm space-y-1">
            {t.lab_orders.map((l) => (
              <li key={l.id} className="flex justify-between">
                <span>Test #{l.test}</span>
                <span className="text-slate-500">{l.status}</span>
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
''')

print("==> Done. Refresh your browser.")