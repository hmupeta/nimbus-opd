import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";
import { useNavigate } from "react-router-dom";

export default function Appointments() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [showForm, setShowForm] = useState(false);

  const appts = useQuery({
    queryKey: ["appointments"],
    queryFn: async () => (await api.get<Paginated<any>>("/appointments/")).data.results,
  });

  const patients = useQuery({
    queryKey: ["patients", "all"],
    queryFn: async () => (await api.get<Paginated<any>>("/patients/")).data.results,
  });

  const doctors = useQuery({
    queryKey: ["users", "doctors"],
    queryFn: async () => (await api.get<Paginated<any>>("/users/?role=doctor")).data.results,
  });

  const createAppt = useMutation({
    mutationFn: async (payload: any) => {
      await api.post("/appointments/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
      setShowForm(false);
    },
  });

  const checkIn = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post(`/appointments/${id}/check-in/`);
      return data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
      qc.invalidateQueries({ queryKey: ["visits"] });
      nav(`/visits/${data.visit_id}`);
    },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    // Combine date and time
    const dateStr = fd.get("date");
    const timeStr = fd.get("time");
    const start = new Date(`${dateStr}T${timeStr}:00Z`).toISOString();
    const end = new Date(new Date(start).getTime() + 30 * 60000).toISOString(); // +30 mins

    createAppt.mutate({
      patient: Number(fd.get("patient")),
      doctor: Number(fd.get("doctor")),
      scheduled_start: start,
      scheduled_end: end,
      reason: String(fd.get("reason")),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Appointments</h1>
        <button onClick={() => setShowForm((v) => !v)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700">+ Book Appointment</button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-lg p-6 space-y-4 shadow-sm max-w-2xl">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm">
              <span className="text-slate-600">Patient</span>
              <select name="patient" required className="mt-1 w-full border rounded px-3 py-2">
                <option value="">Select Patient...</option>
                {patients.data?.map((p: any) => <option key={p.id} value={p.id}>{p.full_name} ({p.mrn})</option>)}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-slate-600">Doctor</span>
              <select name="doctor" required className="mt-1 w-full border rounded px-3 py-2">
                <option value="">Select Doctor...</option>
                {doctors.data?.map((d: any) => <option key={d.id} value={d.id}>Dr. {d.first_name} {d.last_name}</option>)}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-slate-600">Date</span>
              <input type="date" name="date" required className="mt-1 w-full border rounded px-3 py-2" />
            </label>
            <label className="text-sm">
              <span className="text-slate-600">Time</span>
              <input type="time" name="time" required className="mt-1 w-full border rounded px-3 py-2" />
            </label>
          </div>
          <label className="text-sm block">
            <span className="text-slate-600">Reason for visit</span>
            <input name="reason" className="mt-1 w-full border rounded px-3 py-2" placeholder="E.g. Routine checkup" />
          </label>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 border rounded text-slate-600 hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={createAppt.isPending} className="px-4 py-2 bg-sky-600 text-white rounded hover:bg-sky-700">Book</button>
          </div>
        </form>
      )}

      {appts.isLoading && <p className="text-slate-500">Loading...</p>}
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Date & Time</th>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Doctor</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {appts.data?.map((a: any) => (
              <tr key={a.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{new Date(a.scheduled_start).toLocaleString()}</td>
                <td className="px-4 py-3">{a.patient_name}</td>
                <td className="px-4 py-3">{a.doctor_name}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded ${a.status === 'scheduled' ? 'bg-sky-100 text-sky-700' : 'bg-emerald-100 text-emerald-700'}`}>{a.status}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  {a.status === "scheduled" && (
                    <button onClick={() => checkIn.mutate(a.id)} disabled={checkIn.isPending} className="bg-emerald-600 text-white text-xs px-3 py-1.5 rounded hover:bg-emerald-700">Check In</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
