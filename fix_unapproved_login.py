#!/usr/bin/env python3
"""
fix_unapproved_login.py -- Block unapproved tenants at login and show a clear error.
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

# ─── 1. Fix backend login logic (api/tokens.py) ────────────────────────
print("==> Patching api/tokens.py")
tokens_path = OPD / "api" / "tokens.py"
tokens_content = '''\
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import serializers


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Block login if the tenant is not active (pending approval/payment)
        if self.user.tenant and not self.user.tenant.is_active:
            raise serializers.ValidationError(
                {"detail": "Your clinic is pending approval or payment. Please contact the Platform Administrator."}
            )
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.get_full_name() or user.email
        token["is_platform_admin"] = user.is_platform_admin
        return token


class TenantTokenObtainPairView(TokenObtainPairView):
    serializer_class = TenantTokenObtainPairSerializer
'''
tokens_path.write_text(tokens_content, encoding="utf-8")
print("   patched api/tokens.py (added tenant.is_active check)")

# ─── 2. Fix frontend error display (Login.tsx) ─────────────────────────
print("==> Patching frontend/src/pages/Login.tsx")
login_path = FRONTEND / "src" / "pages" / "Login.tsx"
login_content = '''\
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
      nav("/dashboard", { replace: true });
    } catch (err: any) {
      // Extract exact error from DRF (could be in detail or non_field_errors)
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
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <form
        onSubmit={onSubmit}
        className="bg-white p-8 rounded-xl shadow-lg border border-slate-200 w-full max-w-sm space-y-4"
      >
        <h1 className="text-2xl font-bold text-slate-800 text-center mb-2">Sign in</h1>
        
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
login_path.write_text(login_content, encoding="utf-8")
print("   patched Login.tsx (extracts exact error message from DRF)")

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(auth): strictly enforce tenant.is_active at login; improve error UI",
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
print("1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")
print("\nOnce deployed:")
print("1. Try to log in with the unapproved clinic's email/password.")
print("   -> You will see a red box: 'Your clinic is pending approval...'")
print("2. Log in as superadmin@nimbus.local / demo -> /platform -> Approve clinic.")
print("3. Log in again with the clinic's email -> Access granted.")