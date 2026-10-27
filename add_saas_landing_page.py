#!/usr/bin/env python3
"""
add_saas_landing_page.py -- Add public tenant registration API and React Landing Page.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
if not FRONTEND.exists():
    sys.exit(f"Frontend not found at {FRONTEND}.")


def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")


# ─── 1. BACKEND: Registration API ──────────────────────────────────────
print("==> Adding TenantRegistrationView to api/views.py")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

if "class TenantRegistrationView(APIView):" not in v:
    reg_view = '''
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

class TenantRegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from tenants.models import Tenant, TenantSettings, User
        from common.context import db_tenant_context
        from django.db import transaction
        from django.contrib.auth.hashers import make_password
        
        data = request.data
        clinic_name = data.get("clinic_name")
        clinic_code = data.get("clinic_code", "").lower().replace(" ", "-")
        email = data.get("email")
        password = data.get("password")
        first_name = data.get("first_name", "Clinic")
        last_name = data.get("last_name", "Admin")

        if not clinic_name or not clinic_code or not email or not password:
            return Response({"detail": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        if Tenant.objects.filter(code=clinic_code).exists():
            return Response({"detail": "Clinic code already taken. Try another."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({"detail": "Email already registered."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # 1. Create Tenant
                tenant = Tenant.objects.create(code=clinic_code, name=clinic_name)
                
                # 2. Create Admin User
                user = User.objects.create(
                    email=email, password=make_password(password),
                    first_name=first_name, last_name=last_name,
                    tenant=tenant, role="admin", is_staff=True, is_superuser=True
                )

                # 3. Create Settings inside tenant context
                with db_tenant_context(tenant):
                    TenantSettings.objects.create(tenant=tenant, timezone="UTC", currency_code="USD")

            return Response({"detail": "Clinic registered successfully! You can now log in."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

'''
    # Insert the view before the first viewset
    v = v.replace("class TenantViewSet(viewsets.ReadOnlyModelViewSet):", reg_view + "\nclass TenantViewSet(viewsets.ReadOnlyModelViewSet):")
    vp.write_text(v, encoding="utf-8")

print("==> Wiring TenantRegistrationView to api/urls.py")
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "TenantRegistrationView" not in u:
    u = u.replace(
        "from .views import (",
        "from .views import (\n    TenantRegistrationView,"
    )
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n    path('auth/register/', TenantRegistrationView.as_view(), name='register'),"
    )
    up.write_text(u, encoding="utf-8")

# ─── 2. FRONTEND: Landing Page ─────────────────────────────────────────
print("==> Creating LandingPage.tsx")
write_frontend("src/pages/LandingPage.tsx", '''\
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";

export default function LandingPage() {
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  async function onRegister(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const fd = new FormData(e.currentTarget);
    
    try {
      await axios.post("/api/auth/register/", {
        clinic_name: fd.get("clinic_name"),
        clinic_code: fd.get("clinic_code"),
        first_name: fd.get("first_name"),
        last_name: fd.get("last_name"),
        email: fd.get("email"),
        password: fd.get("password"),
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed. Check your details.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Navbar */}
      <header className="bg-white border-b px-8 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm">
        <div className="text-2xl font-bold text-sky-700 tracking-tight">OPD Cloud</div>
        <div className="space-x-4">
          <Link to="/login" className="text-slate-600 font-medium hover:text-sky-700">Sign In</Link>
          <button onClick={() => setShowForm(true)} className="bg-sky-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-sky-700 shadow-sm transition">Get Started</button>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="py-24 px-6 text-center max-w-4xl mx-auto">
          <h1 className="text-5xl font-extrabold text-slate-900 leading-tight mb-6">
            The Modern Operating System for <span className="text-sky-600">Outpatient Clinics</span>
          </h1>
          <p className="text-xl text-slate-600 mb-10 max-w-2xl mx-auto">
            Streamline patient registration, triage, lab requests, pharmacy dispensing, and billing with one secure, multi-tenant platform.
          </p>
          <button onClick={() => setShowForm(true)} className="bg-sky-600 text-white px-8 py-4 rounded-lg text-lg font-bold hover:bg-sky-700 shadow-lg transition transform hover:-translate-y-1">
            Register Your Clinic Today
          </button>
        </section>

        {/* Features */}
        <section className="py-20 bg-white border-y border-slate-200">
          <div className="max-w-6xl mx-auto px-6 grid md:grid-cols-3 gap-12 text-center">
            <div>
              <div className="w-14 h-14 bg-sky-100 text-sky-600 rounded-xl flex items-center justify-center mx-auto mb-4 text-2xl">🏥</div>
              <h3 className="text-xl font-bold mb-2">Clinical Workflow</h3>
              <p className="text-slate-500">From reception to doctor consultation, vitals, and dispensing—fully automated queues.</p>
            </div>
            <div>
              <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-xl flex items-center justify-center mx-auto mb-4 text-2xl">💳</div>
              <h3 className="text-xl font-bold mb-2">Billing & Insurance</h3>
              <p className="text-slate-500">Auto-generated invoices, cash/Stripe/MoMo payments, and seamless insurance claims.</p>
            </div>
            <div>
              <div className="w-14 h-14 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center mx-auto mb-4 text-2xl">🔒</div>
              <h3 className="text-xl font-bold mb-2">Enterprise Security</h3>
              <p className="text-slate-500">Row-Level Security isolates your clinic's data. Full audit trails for every action.</p>
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section className="py-24 px-6 max-w-6xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-12">Simple, Transparent Pricing</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <PriceCard name="Basic" price="$49" desc="Perfect for small practices." features={["1 Doctor", "Up to 500 Patients/mo", "Basic Reporting"]} />
            <PriceCard name="Pro" price="$99" desc="For growing clinics." features={["Up to 5 Doctors", "Unlimited Patients", "SMS Notifications", "Insurance Claims"]} highlighted={true} />
            <PriceCard name="Enterprise" price="Custom" desc="For hospitals and chains." features={["Unlimited Doctors", "Multi-Branch", "Dedicated Support", "Custom Integrations"]} />
          </div>
        </section>
      </main>

      <footer className="bg-slate-900 text-slate-400 py-8 text-center text-sm">
        <p>© {new Date().getFullYear()} OPD Cloud. All rights reserved.</p>
        <p className="mt-2">By using this service, you agree to our <a href="#" className="underline hover:text-white">Terms & Conditions</a> and <a href="#" className="underline hover:text-white">Privacy Policy</a>.</p>
      </footer>

      {/* Registration Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-slate-800">Register Clinic</h2>
              <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-600 text-xl">✕</button>
            </div>
            
            {success ? (
              <div className="text-center py-8">
                <div className="text-5xl mb-4">🎉</div>
                <h3 className="text-xl font-bold text-emerald-600 mb-2">Clinic Registered!</h3>
                <p className="text-slate-600 mb-6">Your account is ready. You can now log in and start configuring your clinic.</p>
                <Link to="/login" className="bg-sky-600 text-white px-6 py-2 rounded hover:bg-sky-700 w-full inline-block">Go to Login</Link>
              </div>
            ) : (
              <form onSubmit={onRegister} className="space-y-4">
                {error && <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{error}</div>}
                
                <div className="grid grid-cols-2 gap-4">
                  <label className="block text-sm">
                    <span className="text-slate-600">Clinic Name</span>
                    <input name="clinic_name" required placeholder="City Health Clinic" className="mt-1 w-full border rounded px-3 py-2" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-slate-600">Short Code</span>
                    <input name="clinic_code" required placeholder="city-health" className="mt-1 w-full border rounded px-3 py-2" />
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <label className="block text-sm">
                    <span className="text-slate-600">First Name</span>
                    <input name="first_name" required placeholder="John" className="mt-1 w-full border rounded px-3 py-2" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-slate-600">Last Name</span>
                    <input name="last_name" required placeholder="Doe" className="mt-1 w-full border rounded px-3 py-2" />
                  </label>
                </div>

                <label className="block text-sm">
                  <span className="text-slate-600">Admin Email</span>
                  <input type="email" name="email" required placeholder="admin@cityhealth.com" className="mt-1 w-full border rounded px-3 py-2" />
                </label>

                <label className="block text-sm">
                  <span className="text-slate-600">Password</span>
                  <input type="password" name="password" required minLength={6} className="mt-1 w-full border rounded px-3 py-2" />
                </label>

                <label className="flex items-start gap-2 text-sm text-slate-600 mt-2">
                  <input type="checkbox" required className="mt-1" />
                  <span>I agree to the <a href="#" className="text-sky-600 hover:underline">Terms & Conditions</a> and <a href="#" className="text-sky-600 hover:underline">Privacy Policy</a>.</span>
                </label>

                <button type="submit" disabled={busy} className="w-full bg-sky-600 text-white py-2 rounded font-bold hover:bg-sky-700 disabled:opacity-50 mt-4">
                  {busy ? "Creating Clinic..." : "Register Clinic"}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PriceCard({ name, price, desc, features, highlighted = false }: any) {
  return (
    <div className={`border rounded-2xl p-8 ${highlighted ? 'border-sky-600 shadow-xl relative bg-white transform md:-translate-y-4' : 'border-slate-200 bg-slate-50'}`}>
      {highlighted && <div className="absolute top-0 left-1/2 -translate-x-1/2 bg-sky-600 text-white px-4 py-1 rounded-b-lg text-xs font-bold tracking-wide uppercase">Most Popular</div>}
      <h3 className="text-xl font-bold text-slate-800 mb-2">{name}</h3>
      <div className="text-4xl font-extrabold text-slate-900 mb-2">{price}<span className="text-lg text-slate-500 font-medium">{price !== 'Custom' && '/mo'}</span></div>
      <p className="text-slate-500 mb-6 text-sm">{desc}</p>
      <ul className="space-y-3 mb-8 text-left text-sm">
        {features.map((f: string) => (
          <li key={f} className="flex items-center gap-2 text-slate-700">
            <span className="text-emerald-500">✓</span> {f}
          </li>
        ))}
      </ul>
      <button className={`w-full py-2 rounded-lg font-medium border ${highlighted ? 'bg-sky-600 text-white border-transparent hover:bg-sky-700' : 'border-slate-300 text-slate-700 hover:bg-slate-100'}`}>
        Choose {name}
      </button>
    </div>
  );
}
''')

# ─── 3. FRONTEND: Update App.tsx Routing ───────────────────────────────
print("==> Updating App.tsx to route unauthenticated users to LandingPage")
ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")

if "LandingPage" not in a:
    a = a.replace(
        'import Login from "./pages/Login";',
        'import Login from "./pages/Login";\nimport LandingPage from "./pages/LandingPage";'
    )
    # Add public route for /
    a = a.replace(
        '<Route path="/login" element={<Login />} />',
        '<Route path="/" element={<LandingPage />} />\n      <Route path="/login" element={<Login />} />'
    )
    # Rename the protected dashboard route so it doesn't clash with the landing page
    a = a.replace(
        '<Route path="/" element={<Dashboard />} />',
        '<Route path="/dashboard" element={<Dashboard />} />'
    )
    # Update the fallback redirect
    a = a.replace(
        '<Route path="*" element={<Navigate to="/" replace />} />',
        '<Route path="*" element={<Navigate to="/dashboard" replace />} />'
    )
    ap.write_text(a, encoding="utf-8")

# ─── 4. FRONTEND: Fix Navigation Links ─────────────────────────────────
print("==> Updating Navigation links to point to /dashboard")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if 'to="/"' in l:
    l = l.replace('<Link to="/" className="text-lg font-bold text-sky-700">OPD</Link>', '<Link to="/dashboard" className="text-lg font-bold text-sky-700">OPD</Link>')
    l = l.replace('<NavLink to="/" end className={linkClass}>Dashboard</NavLink>', '<NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>')
    lp.write_text(l, encoding="utf-8")

print("==> Done. Refresh your browser.")