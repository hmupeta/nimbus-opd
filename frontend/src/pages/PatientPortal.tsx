import { FormEvent, useState } from "react";
import axios from "axios";

export default function PatientPortal() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onLogin(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const fd = new FormData(e.currentTarget);

    try {
      const res = await axios.post("/api/public/portal/", {
        clinic_code: fd.get("clinic_code"),
        mrn: fd.get("mrn"),
        dob: fd.get("dob"),
      });
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Could not find your records.");
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <form
          onSubmit={onLogin}
          className="bg-white p-8 rounded-xl shadow-lg border w-full max-w-md space-y-4"
        >
          <div className="text-center mb-6">
            <div className="text-3xl font-bold text-sky-600 mb-2">Nimbus OPD</div>
            <h1 className="text-xl text-slate-600">Patient Portal</h1>
          </div>
          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{error}</div>
          )}
          <label className="block text-sm">
            <span className="text-slate-600">Clinic Code (e.g., demo)</span>
            <input
              name="clinic_code"
              required
              placeholder="demo"
              className="mt-1 w-full border rounded px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">MRN (Medical Record Number)</span>
            <input
              name="mrn"
              required
              placeholder="MRN-000001"
              className="mt-1 w-full border rounded px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">Date of Birth</span>
            <input
              type="date"
              name="dob"
              required
              className="mt-1 w-full border rounded px-3 py-2"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="w-full bg-sky-600 text-white py-2 rounded font-bold hover:bg-sky-700 disabled:opacity-50 mt-4"
          >
            {busy ? "Searching…" : "Access My Records"}
          </button>
          <div className="text-center mt-4">
            <a href="/" className="text-sm text-slate-500 hover:underline">
              Back to Home
            </a>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">
              Welcome, {data.patient_name}
            </h1>
            <p className="text-slate-500">
              {data.clinic_name} • {data.mrn}
            </p>
          </div>
          <button
            onClick={() => setData(null)}
            className="text-sm text-red-600 hover:underline"
          >
            Log out
          </button>
        </div>

        <h2 className="text-xl font-semibold text-slate-700 mt-8">Visit History</h2>

        {data.history.length === 0 && (
          <p className="text-slate-500">No past visits found.</p>
        )}

        <div className="space-y-4">
          {data.history.map((v: any, idx: number) => (
            <div
              key={idx}
              className="bg-white p-6 rounded-xl shadow-sm border"
            >
              <div className="flex justify-between border-b pb-3 mb-3">
                <div>
                  <h3 className="font-bold text-lg">
                    {new Date(v.date).toLocaleDateString()}
                  </h3>
                  <p className="text-sm text-slate-500">Seen by {v.doctor}</p>
                </div>
                <span className="text-sm bg-slate-100 px-2 py-0.5 rounded h-fit">
                  {v.visit_no}
                </span>
              </div>

              <div className="grid md:grid-cols-3 gap-4 text-sm">
                {v.labs.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-slate-700 mb-2">Lab Results</h4>
                    <ul className="space-y-1">
                      {v.labs.map((l: any, i: number) => (
                        <li key={i} className="text-slate-600">
                          <b>{l.test}:</b>{" "}
                          {l.result ? `${l.result} ${l.unit || ""}` : "Pending"}
                          {l.flag && (
                            <span className="ml-1 text-xs font-bold text-red-500">
                              ({l.flag})
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {v.radiology.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-slate-700 mb-2">Radiology</h4>
                    <ul className="space-y-1">
                      {v.radiology.map((r: any, i: number) => (
                        <li key={i} className="text-slate-600">
                          <b>{r.exam}:</b> {r.impression || "Pending"}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {v.prescriptions.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-slate-700 mb-2">Prescriptions</h4>
                    <ul className="space-y-1">
                      {v.prescriptions.map((m: any, i: number) => (
                        <li key={i} className="text-slate-600">
                          <b>{m.medicine}</b> ({m.dose}) - {m.quantity} qty
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
