#!/usr/bin/env python3
"""
create_missing_pages.py
  - Creates WaitingRoom.tsx and PatientPortal.tsx if they're missing
  - Verifies every page imported in App.tsx actually exists
  - Pushes
"""
from __future__ import annotations
import os
import re
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

FRONTEND = OPD / "frontend"
PAGES = FRONTEND / "src" / "pages"
PAGES.mkdir(parents=True, exist_ok=True)

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

def write_page(name: str, content: str):
    p = PAGES / name
    if p.exists() and p.stat().st_size > 100:
        print(f"   [skip] {name} already exists ({p.stat().st_size} bytes)")
        return
    p.write_text(content, encoding="utf-8")
    print(f"   wrote src/pages/{name}")

# ─── 1. Create WaitingRoom.tsx (public TV display) ─────────────────────
print("==> Creating WaitingRoom.tsx")
WAITING_ROOM = r'''\
import { useQuery } from "@tanstack/react-query";
import axios from "axios";

export default function WaitingRoom() {
  const { data } = useQuery({
    queryKey: ["waiting-room"],
    queryFn: async () => (await axios.get("/api/public/waiting-room/")).data,
    refetchInterval: 5000,
  });

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col p-8 font-sans">
      <header className="flex justify-between items-center border-b border-slate-700 pb-4 mb-8">
        <div className="text-3xl font-bold text-sky-400">Nimbus OPD Cloud</div>
        <div className="text-xl text-slate-400">{new Date().toLocaleTimeString()}</div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12 flex-1">
        <div className="flex flex-col items-center">
          <h2 className="text-4xl font-extrabold text-emerald-400 mb-8 tracking-wider">
            NOW SERVING
          </h2>
          <div className="w-full space-y-6">
            {!data?.now_serving || data.now_serving.length === 0 ? (
              <div className="text-center text-slate-500 text-2xl mt-12">
                Waiting for next patient…
              </div>
            ) : (
              data.now_serving.map((item: any) => (
                <div
                  key={item.token}
                  className="bg-emerald-900/40 border-2 border-emerald-500 rounded-2xl p-8 flex justify-between items-center animate-pulse"
                >
                  <div>
                    <div className="text-6xl font-black text-white">{item.token}</div>
                    <div className="text-2xl text-emerald-200 mt-2">{item.patient}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-white">{item.doctor}</div>
                    <div className="text-emerald-300">Room 1</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="flex flex-col">
          <h2 className="text-3xl font-bold text-sky-400 mb-8 tracking-wider">
            WAITING QUEUE
          </h2>
          <div className="bg-slate-800 rounded-2xl p-6 flex-1">
            {!data?.waiting || data.waiting.length === 0 ? (
              <div className="text-center text-slate-500 text-xl mt-12">
                Queue is empty.
              </div>
            ) : (
              <ul className="space-y-4">
                {data.waiting.map((item: any, idx: number) => (
                  <li
                    key={item.token}
                    className="flex justify-between items-center text-xl border-b border-slate-700 pb-3"
                  >
                    <div className="flex items-center gap-4">
                      <span className="text-slate-500 font-mono text-lg">{idx + 1}.</span>
                      <span className="font-bold text-white">{item.token}</span>
                      <span className="text-slate-400">{item.patient}</span>
                    </div>
                    <span className="text-slate-500">{item.doctor}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <footer className="mt-8 text-center text-slate-500">
        Please keep an eye on this screen. You will be called shortly.
      </footer>
    </div>
  );
}
'''
write_page("WaitingRoom.tsx", WAITING_ROOM)

# ─── 2. Create PatientPortal.tsx (public patient lookup) ───────────────
print("==> Creating PatientPortal.tsx")
PATIENT_PORTAL = r'''\
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
'''
write_page("PatientPortal.tsx", PATIENT_PORTAL)

# ─── 3. Verify EVERY import in App.tsx has a matching file ─────────────
print("\n==> Verifying all App.tsx imports resolve to real files")
app = FRONTEND / "src" / "App.tsx"
app_content = app.read_text(encoding="utf-8")

import_pattern = re.compile(r'import\s+\w+\s+from\s+["\'](\./[^"\']+)["\']')
imports = import_pattern.findall(app_content)

missing = []
for rel_path in imports:
    # Strip ./ and add .tsx extension
    clean = rel_path.lstrip("./")
    # Try .tsx, .ts
    candidates = [
        FRONTEND / "src" / f"{clean}.tsx",
        FRONTEND / "src" / f"{clean}.ts",
    ]
    if not any(c.exists() for c in candidates):
        missing.append(rel_path)

if missing:
    print("   ❌ Missing files referenced by App.tsx:")
    for m in missing:
        print(f"      {m}")
    sys.exit("Cannot build — create the missing files first.")
print(f"   ✓ All {len(imports)} imports resolve")

# ─── 4. Verify Layout.tsx imports ──────────────────────────────────────
print("==> Verifying Layout.tsx imports")
layout = FRONTEND / "src" / "components" / "Layout.tsx"
if layout.exists():
    layout_content = layout.read_text(encoding="utf-8")
    layout_imports = import_pattern.findall(layout_content)
    layout_missing = []
    for rel_path in layout_imports:
        clean = rel_path.lstrip("./")
        candidates = [
            FRONTEND / "src" / "components" / f"{clean}.tsx",
            FRONTEND / "src" / "components" / f"{clean}.ts",
            FRONTEND / "src" / f"{clean}.tsx",
        ]
        if not any(c.exists() for c in candidates):
            layout_missing.append(rel_path)
    if layout_missing:
        print("   ❌ Missing files referenced by Layout.tsx:")
        for m in layout_missing:
            print(f"      {m}")
    else:
        print(f"   ✓ All {len(layout_imports)} Layout imports resolve")

# ─── 5. List all pages present ─────────────────────────────────────────
print("\n==> All files in src/pages/")
for f in sorted(PAGES.glob("*.tsx")):
    size = f.stat().st_size
    print(f"   {f.name:30} {size:>6} bytes")

# ─── 6. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(frontend): create missing WaitingRoom.tsx and PatientPortal.tsx",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")