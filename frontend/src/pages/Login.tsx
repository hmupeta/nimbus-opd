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
