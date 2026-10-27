#!/usr/bin/env python3
"""
create_frontend.py -- scaffold a React + Vite + Tailwind SPA in ../frontend.
Windows-safe: resolves npm via shutil.which (which honours PATHEXT).
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

FRONTEND = BACKEND.parent / "frontend"

# ─── Ensure portable Node is on PATH for this process ──────────────────
NODE_DIR = Path.home() / "Documents" / "django" / "nodejs"
if (NODE_DIR / "node.exe").exists():
    os.environ["PATH"] = str(NODE_DIR) + os.pathsep + os.environ.get("PATH", "")


def sh(*cmd, cwd=None):
    """Windows-safe subprocess runner: resolves 'npm' → 'npm.CMD' etc."""
    cmd = [shutil.which(str(cmd[0])) or str(cmd[0])] + [str(c) for c in cmd[1:]]
    print("   $", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd or FRONTEND)


def write(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")


# ─── 0. Sanity checks ─────────────────────────────────────────────────
print("==> Checking Node.js")
if not shutil.which("node"):
    sys.exit("node not found. Run get_portable_node.py first, or add nodejs to PATH.")
if not shutil.which("npm"):
    sys.exit("npm not found. Run get_portable_node.py first, or add nodejs to PATH.")
print("    node:", subprocess.check_output(["node", "--version"], text=True).strip())
print("    npm: ", subprocess.check_output([shutil.which("npm"), "--version"], text=True).strip())

# ─── 1. Create folder structure ────────────────────────────────────────
print(f"==> Creating {FRONTEND}")
FRONTEND.mkdir(parents=True, exist_ok=True)
for sub in ("src", "src/pages", "src/api", "src/components"):
    (FRONTEND / sub).mkdir(parents=True, exist_ok=True)

# ─── 2. Build tooling ──────────────────────────────────────────────────
write("package.json", '''\
{
  "name": "opd-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "axios": "^1.7.7",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  },
  "devDependencies": {
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.6.2",
    "vite": "^5.4.8"
  }
}
''')

write("vite.config.ts", '''\
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
''')

write("tsconfig.json", '''\
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
''')

write("tsconfig.node.json", '''\
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
''')

write("tailwind.config.js", '''\
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
''')

write("postcss.config.js", '''\
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
''')

write("index.html", '''\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OPD</title>
  </head>
  <body class="bg-slate-50">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
''')

write(".gitignore", "node_modules\ndist\n.env\n")

# ─── 3. src entrypoint & styles ────────────────────────────────────────
write("src/index.css", '''\
@tailwind base;
@tailwind components;
@tailwind utilities;

body { @apply text-slate-800; }
''')

write("src/main.tsx", '''\
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
''')

# ─── 4. API client ─────────────────────────────────────────────────────
write("src/api/client.ts", '''\
import axios from "axios";

const TOKEN_KEY = "opd.access";
const REFRESH_KEY = "opd.refresh";

export const api = axios.create({ baseURL: "/api" });

export function getAccess() { return localStorage.getItem(TOKEN_KEY); }
export function getRefresh() { return localStorage.getItem(REFRESH_KEY); }
export function setTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

api.interceptors.request.use((config) => {
  const token = getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes("/auth/")
    ) {
      const refresh = getRefresh();
      if (!refresh) {
        clearTokens();
        window.location.href = "/login";
        return Promise.reject(error);
      }
      original._retry = true;
      try {
        const { data } = await axios.post("/api/auth/refresh/", { refresh });
        setTokens(data.access, data.refresh ?? refresh);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch (e) {
        clearTokens();
        window.location.href = "/login";
        return Promise.reject(e);
      }
    }
    return Promise.reject(error);
  }
);
''')

write("src/api/auth.ts", '''\
import axios from "axios";
import { setTokens, clearTokens } from "./client";

export interface JWTPayload {
  user_id: number;
  email: string;
  role: string;
  tenant_id: string | null;
  full_name: string;
  exp: number;
}

export async function login(email: string, password: string): Promise<JWTPayload> {
  const { data } = await axios.post("/api/auth/login/", { email, password });
  setTokens(data.access, data.refresh);
  return decode(data.access);
}

export function logout() { clearTokens(); }

export function decode(token: string): JWTPayload {
  const payload = token.split(".")[1];
  const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(json) as JWTPayload;
}

export function currentUser(): JWTPayload | null {
  const tok = localStorage.getItem("opd.access");
  if (!tok) return null;
  try {
    const p = decode(tok);
    if (p.exp * 1000 < Date.now()) return null;
    return p;
  } catch { return null; }
}
''')

write("src/api/types.ts", '''\
export interface Patient {
  id: number;
  mrn: string;
  first_name: string;
  last_name: string;
  full_name: string;
  sex: string;
  dob: string | null;
  phone: string;
  email: string;
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

# ─── 5. Components ─────────────────────────────────────────────────────
write("src/components/Layout.tsx", '''\
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { currentUser, logout } from "../api/auth";

export default function Layout() {
  const nav = useNavigate();
  const user = currentUser();

  function handleLogout() { logout(); nav("/login"); }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium ${
      isActive ? "bg-sky-100 text-sky-700" : "text-slate-600 hover:bg-slate-100"
    }`;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6">
          <Link to="/" className="text-lg font-bold text-sky-700">OPD</Link>
          <nav className="flex gap-2">
            <NavLink to="/" end className={linkClass}>Dashboard</NavLink>
            <NavLink to="/patients" className={linkClass}>Patients</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-slate-600">
            {user ? (
              <>
                <span>{user.full_name || user.email}</span>
                <span className="text-xs bg-slate-100 px-2 py-0.5 rounded">{user.role}</span>
                <button
                  onClick={handleLogout}
                  className="px-3 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200"
                >
                  Sign out
                </button>
              </>
            ) : (
              <Link to="/login" className="text-sky-700 font-medium">Sign in</Link>
            )}
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
''')

write("src/components/ProtectedRoute.tsx", '''\
import { Navigate, Outlet } from "react-router-dom";
import { currentUser } from "../api/auth";

export default function ProtectedRoute() {
  return currentUser() ? <Outlet /> : <Navigate to="/login" replace />;
}
''')

# ─── 6. Pages ──────────────────────────────────────────────────────────
write("src/pages/Login.tsx", '''\
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth";

export default function Login() {
  const [email, setEmail] = useState("admin@demo.local");
  const [password, setPassword] = useState("demo");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null); setBusy(true);
    try {
      await login(email, password);
      nav("/", { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Login failed. Check credentials.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form
        onSubmit={onSubmit}
        className="bg-white p-8 rounded-lg border border-slate-200 w-full max-w-sm space-y-4"
      >
        <h1 className="text-xl font-semibold text-slate-800">Sign in</h1>
        {error && <div className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</div>}
        <label className="block text-sm">
          <span className="text-slate-600">Email</span>
          <input type="email" required value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded border border-slate-300 px-3 py-2" />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600">Password</span>
          <input type="password" required value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded border border-slate-300 px-3 py-2" />
        </label>
        <button disabled={busy}
          className="w-full rounded bg-sky-600 text-white py-2 hover:bg-sky-700 disabled:opacity-50">
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-xs text-slate-500">Demo: admin@demo.local / demo</p>
      </form>
    </div>
  );
}
''')

write("src/pages/Dashboard.tsx", '''\
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DashboardSummary, Paginated, Visit } from "../api/types";

export default function Dashboard() {
  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get<DashboardSummary>("/reports/dashboard/")).data,
  });

  const visits = useQuery({
    queryKey: ["visits", "open"],
    queryFn: async () => {
      const openStatuses = ["open", "triaged", "in_consultation", "awaiting_results", "pharmacy"];
      const results = await Promise.all(
        openStatuses.map((s) =>
          api.get<Paginated<Visit>>(`/visits/?status=${s}`).then((r) => r.data.results)
        )
      );
      return results.flat();
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      {summary.isLoading && <p className="text-slate-500">Loading…</p>}
      {summary.data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Today's visits" value={summary.data.census.total} />
          <Stat label="Waiting" value={summary.data.census.waiting} />
          <Stat label="In consultation" value={summary.data.census.in_consultation} />
          <Stat label="Revenue today" value={`ZMW ${summary.data.revenue.today}`} />
        </div>
      )}
      <section>
        <h2 className="text-lg font-semibold mb-2">Active visits</h2>
        {visits.isLoading && <p className="text-slate-500">Loading…</p>}
        {visits.data && visits.data.length === 0 && (
          <p className="text-slate-500">No active visits.</p>
        )}
        <ul className="divide-y border rounded-lg bg-white">
          {visits.data?.map((v) => (
            <li key={v.id}>
              <Link to={`/visits/${v.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-slate-50">
                <div>
                  <p className="font-medium">{v.patient_name}</p>
                  <p className="text-sm text-slate-500">{v.visit_no} · {v.visit_type}</p>
                </div>
                <span className="text-xs bg-sky-100 text-sky-700 rounded px-2 py-0.5">
                  {v.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}
''')

write("src/pages/Patients.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Paginated, Patient, Visit } from "../api/types";

export default function Patients() {
  const [q, setQ] = useState("");
  const [showForm, setShowForm] = useState(false);
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
    mutationFn: async (payload: Partial<Patient>) => {
      const { data } = await api.post<Patient>("/patients/", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      setShowForm(false);
    },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createPatient.mutate({
      first_name: String(fd.get("first_name") || ""),
      last_name: String(fd.get("last_name") || ""),
      sex: String(fd.get("sex") || "O"),
      phone: String(fd.get("phone") || ""),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Patients</h1>
        <input placeholder="Search name or MRN…" value={q}
          onChange={(e) => setQ(e.target.value)}
          className="ml-auto border rounded px-3 py-2 w-64" />
        <button onClick={() => setShowForm((v) => !v)}
          className="rounded bg-sky-600 text-white px-3 py-2 hover:bg-sky-700">
          + New patient
        </button>
      </div>

      {showForm && (
        <form onSubmit={onCreate}
          className="bg-white border rounded-lg p-4 grid grid-cols-2 gap-3">
          <input name="first_name" placeholder="First name" required
            className="border rounded px-3 py-2" />
          <input name="last_name" placeholder="Last name" required
            className="border rounded px-3 py-2" />
          <select name="sex" className="border rounded px-3 py-2">
            <option value="M">Male</option>
            <option value="F">Female</option>
            <option value="O">Other</option>
          </select>
          <input name="phone" placeholder="Phone"
            className="border rounded px-3 py-2" />
          <button className="col-span-2 rounded bg-sky-600 text-white py-2 hover:bg-sky-700">
            Save
          </button>
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
                <th />
              </tr>
            </thead>
            <tbody className="divide-y">
              {list.data.results.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-2 font-mono text-xs">{p.mrn}</td>
                  <td className="px-4 py-2">{p.full_name}</td>
                  <td className="px-4 py-2">{p.sex}</td>
                  <td className="px-4 py-2">{p.phone}</td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => startVisit.mutate(p.id)}
                      disabled={startVisit.isPending}
                      className="rounded bg-emerald-600 text-white text-xs px-2 py-1 hover:bg-emerald-700 disabled:opacity-50">
                      Start visit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.data.results.length === 0 && (
            <p className="p-4 text-slate-500">No patients found.</p>
          )}
        </div>
      )}
    </div>
  );
}
''')

write("src/pages/VisitTimeline.tsx", '''\
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Timeline } from "../api/types";

export default function VisitTimeline() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

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

  if (q.isLoading) return <p className="text-slate-500">Loading…</p>;
  if (q.error || !q.data) return <p className="text-red-600">Failed to load.</p>;

  const t = q.data;

  return (
    <div className="space-y-6">
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
          {t.vitals ? (
            <ul className="text-sm space-y-1">
              <li>Temp: {t.vitals.temperature_c}°C</li>
              <li>BP: {t.vitals.systolic}/{t.vitals.diastolic}</li>
              <li>Pulse: {t.vitals.pulse}</li>
              <li>SpO₂: {t.vitals.spo2}%</li>
            </ul>
          ) : (
            <p className="text-sm text-slate-500">Not recorded</p>
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
              <li key={n.id} className="text-sm">
                <p className="font-medium">
                  {n.kind.toUpperCase()} — {new Date(n.created_at).toLocaleString()}
                </p>
                <p><span className="text-slate-500">S:</span> {n.subjective}</p>
                <p><span className="text-slate-500">O:</span> {n.objective}</p>
                <p><span className="text-slate-500">A:</span> {n.assessment}</p>
                <p><span className="text-slate-500">P:</span> {n.plan}</p>
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
      <h2 className="text-sm font-semibold text-slate-600 mb-2">{title}</h2>
      {children}
    </div>
  );
}
''')

# ─── 7. Router ─────────────────────────────────────────────────────────
write("src/App.tsx", '''\
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Patients from "./pages/Patients";
import VisitTimeline from "./pages/VisitTimeline";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/visits/:id" element={<VisitTimeline />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
''')

# ─── 8. Install packages ───────────────────────────────────────────────
print("==> npm install (this may take 1–2 minutes)")
sh("npm", "install")

print()
print("=" * 70)
print("SUCCESS — frontend created at:", FRONTEND)
print()
print("Start the two servers in separate PowerShell windows:")
print()
print("Terminal 1 (backend):")
print("    cd", BACKEND)
print(r"    .\.venv\Scripts\Activate.ps1")
print("    python manage.py runserver")
print()
print("Terminal 2 (frontend):")
print(f'    $env:PATH = "{NODE_DIR};" + $env:PATH')
print("    cd", FRONTEND)
print("    npm run dev")
print()
print("Then open http://localhost:5173")
print("Login: admin@demo.local / demo")
print("=" * 70)