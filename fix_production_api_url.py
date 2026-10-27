#!/usr/bin/env python3
"""
fix_production_api_url.py -- Update frontend to use VITE_API_BASE for API calls.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

FRONTEND = OPD / "frontend"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

# ─── 1. Update src/api/client.ts ───────────────────────────────────────
print("==> Updating src/api/client.ts")
client_path = FRONTEND / "src" / "api" / "client.ts"
client_content = '''\
import axios from "axios";

// Use the production URL from Render, fallback to localhost for dev
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Set global default for raw axios calls
axios.defaults.baseURL = API_BASE;

const TOKEN_KEY = "opd.access";
const REFRESH_KEY = "opd.refresh";

// Create an instance for the app-specific calls
export const api = axios.create({ baseURL: `${API_BASE}/api` });

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
        // Use global axios here so it inherits the baseURL
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
'''
client_path.write_text(client_content, encoding="utf-8")
print("   patched client.ts with VITE_API_BASE")

# ─── 2. Update src/api/auth.ts (Login) ─────────────────────────────────
print("==> Updating src/api/auth.ts")
auth_path = FRONTEND / "src" / "api" / "auth.ts"
auth_content = '''\
import axios from "axios";
import { setTokens, clearTokens } from "./client";

export interface JWTPayload {
  user_id: number;
  email: string;
  role: string;
  tenant_id: string | null;
  full_name: string;
  exp: number;
  is_platform_admin: boolean;
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
'''
auth_path.write_text(auth_content, encoding="utf-8")
print("   patched auth.ts")

# ─── 3. Update LandingPage.tsx (Register) ──────────────────────────────
print("==> Updating LandingPage.tsx")
landing_path = FRONTEND / "src" / "pages" / "LandingPage.tsx"
landing = landing_path.read_text(encoding="utf-8")
# Ensure axios is imported and uses the global default
if "axios.post('/api/auth/register/'" in landing or 'axios.post("/api/auth/register/"' in landing:
    print("   LandingPage already uses relative path, global baseURL will handle it.")
else:
    print("   [WARN] Could not find register axios call in LandingPage.")

# ─── 4. Commit and Push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(frontend): wire up VITE_API_BASE for production API calls",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "rev-parse", "--short", "HEAD")
print(f"\n✅ Pushed: {r.stdout.strip()}")

print("\n" + "=" * 60)
print("NEXT STEPS ON RENDER")
print("=" * 60)
print("1. Open nimbus-frontend → Manual Deploy → Clear build cache & deploy")
print("2. Wait ~2 minutes for the React build to complete.")
print("3. Go to the frontend URL and log in as superadmin@nimbus.local / demo")