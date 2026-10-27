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
