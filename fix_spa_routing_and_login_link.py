#!/usr/bin/env python3
"""
fix_spa_routing_and_login_link.py
  - Adds _redirects file so Render serves index.html for React Router
  - Adds "Back to Home" link on the Login page
  - Pushes to GitHub
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

FRONTEND = OPD / "frontend"
PUBLIC_DIR = FRONTEND / "public"
LOGIN_PAGE = FRONTEND / "src" / "pages" / "Login.tsx"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

# ─── 1. Create the _redirects file for Render ──────────────────────────
print("==> Creating frontend/public/_redirects")
PUBLIC_DIR.mkdir(exist_ok=True)
redirects_file = PUBLIC_DIR / "_redirects"
redirects_file.write_text("/*    /index.html   200\n", encoding="utf-8")
print("   created _redirects (forces SPA routing on Render)")

# ─── 2. Update Login.tsx to add "Back to Home" link ────────────────────
print("==> Updating Login.tsx")
login_content = '''\
import { FormEvent, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
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
      nav("/dashboard", { replace: true });
    } catch (err: any) {
      const data = err?.response?.data;
      let msg = "Login failed. Check credentials.";
      
      if (data?.detail) {
        msg = typeof data.detail === 'string' ? data.detail : data.detail[0];
      } else if (data?.non_field_errors) {
        msg = data.non_field_errors[0];
      }
      
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 p-4">
      
      {/* Back to Home Link */}
      <div className="w-full max-w-sm mb-6">
        <Link to="/" className="text-sm text-slate-500 hover:text-sky-600 flex items-center gap-1 font-medium transition">
          <span>←</span> Back to Home
        </Link>
      </div>

      <form
        onSubmit={onSubmit}
        className="bg-white p-8 rounded-xl shadow-lg border border-slate-200 w-full max-w-sm space-y-4"
      >
        <div className="text-center mb-6">
          <div className="w-10 h-10 bg-sky-600 rounded-lg flex items-center justify-center text-white font-bold text-xl mx-auto mb-3">N</div>
          <h1 className="text-2xl font-bold text-slate-800">Sign in</h1>
        </div>
        
        {error && (
          <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg border border-red-100">
            {error}
          </div>
        )}
        
        <label className="block text-sm">
          <span className="text-slate-600 font-medium">Email</span>
          <input type="email" required value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none" />
        </label>
        
        <label className="block text-sm">
          <span className="text-slate-600 font-medium">Password</span>
          <input type="password" required value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none" />
        </label>
        
        <button disabled={busy}
          className="w-full rounded-lg bg-sky-600 text-white py-2.5 font-bold hover:bg-sky-700 disabled:opacity-50 transition shadow-md">
          {busy ? "Signing in…" : "Sign in"}
        </button>
        
        <p className="text-xs text-slate-500 text-center mt-4">
          Demo: admin@demo.local / demo
        </p>
      </form>
    </div>
  );
}
'''
LOGIN_PAGE.write_text(login_content, encoding="utf-8")
print("   patched Login.tsx (added Back to Home link)")

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(frontend): add SPA _redirects for Render and Back to Home link",
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
print("  1. nimbus-frontend → Manual Deploy → Clear build cache & deploy")
print("  2. Once live, refreshing /login or /dashboard will now work perfectly!")