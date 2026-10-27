#!/usr/bin/env python3
"""
update_nimbus_landing_kwacha.py -- Detailed landing page with ZMW pricing.
"""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    import sys
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

print("==> Rebuilding LandingPage.tsx with detailed content and ZMW pricing")
write_frontend("src/pages/LandingPage.tsx", '''\
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";

export default function LandingPage() {
  const [showForm, setShowForm] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

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
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Navbar */}
      <header className="bg-white border-b px-8 py-4 flex items-center justify-between sticky top-0 z-40 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-sky-600 rounded-lg flex items-center justify-center text-white font-bold text-xl">N</div>
          <div className="text-2xl font-bold text-slate-800 tracking-tight">Nimbus <span className="text-sky-600">OPD Cloud</span></div>
        </div>
        <div className="space-x-6 hidden md:flex items-center">
          <a href="#features" className="text-slate-600 font-medium hover:text-sky-700">Features</a>
          <a href="#highlights" className="text-slate-600 font-medium hover:text-sky-700">Why Nimbus</a>
          <a href="#pricing" className="text-slate-600 font-medium hover:text-sky-700">Pricing</a>
          <Link to="/login" className="text-slate-600 font-medium hover:text-sky-700">Sign In</Link>
          <button onClick={() => setShowForm(true)} className="bg-sky-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-sky-700 shadow-sm transition">Get Started</button>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="py-24 px-6 text-center max-w-5xl mx-auto">
          <div className="inline-block bg-sky-100 text-sky-800 font-semibold px-4 py-1.5 rounded-full text-sm mb-6 shadow-sm">
            Built for Zambian Clinics
          </div>
          <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 leading-tight mb-6">
            Run your clinic from the <span className="text-transparent bg-clip-text bg-gradient-to-r from-sky-600 to-indigo-600">cloud</span>.
          </h1>
          <p className="text-xl text-slate-600 mb-10 max-w-2xl mx-auto">
            Nimbus OPD Cloud streamlines patient registration, triage, lab requests, pharmacy dispensing, and billing—all in one secure, multi-tenant platform.
          </p>
          <button onClick={() => setShowForm(true)} className="bg-sky-600 text-white px-8 py-4 rounded-lg text-lg font-bold hover:bg-sky-700 shadow-lg transition transform hover:-translate-y-1">
            Register Your Clinic Today
          </button>
        </section>

        {/* Why Nimbus Highlights */}
        <section id="highlights" className="py-20 bg-white border-y border-slate-200">
          <div className="max-w-6xl mx-auto px-6">
            <h2 className="text-3xl font-bold text-center mb-4">Why Clinics Choose Nimbus</h2>
            <p className="text-center text-slate-500 mb-12 max-w-2xl mx-auto">We built the features that matter most for outpatient departments, inspired by the best systems globally.</p>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
              <div className="text-center">
                <div className="w-14 h-14 bg-sky-100 text-sky-600 rounded-xl flex items-center justify-center mx-auto mb-4 text-2xl">⏱️</div>
                <h3 className="text-lg font-bold mb-2">Smart Token Queue</h3>
                <p className="text-slate-500 text-sm">Automated token generation per doctor, per day. Reduce crowding at the front desk.</p>
              </div>
              <div className="text-center">
                <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-xl flex items-center justify-center mx-auto mb-4 text-2xl">📋</div>
                <h3 className="text-lg font-bold mb-2">Unified EMR</h3>
                <p className="text-slate-500 text-sm">Vitals, notes, labs, and prescriptions linked to a single patient encounter.</p>
              </div>
              <div className="text-center">
                <div className="w-14 h-14 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center mx-auto mb-4 text-2xl">🔔</div>
                <h3 className="text-lg font-bold mb-2">Doctor Alerts</h3>
                <p className="text-slate-500 text-sm">Instant notifications from Pharmacy and Lab when results are ready.</p>
              </div>
              <div className="text-center">
                <div className="w-14 h-14 bg-rose-100 text-rose-600 rounded-xl flex items-center justify-center mx-auto mb-4 text-2xl">📊</div>
                <h3 className="text-lg font-bold mb-2">Real-time Dashboard</h3>
                <p className="text-slate-500 text-sm">Daily collections, patient footfall, and revenue per doctor at a glance.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Detailed Features */}
        <section id="features" className="py-24 bg-slate-50">
          <div className="max-w-6xl mx-auto px-6">
            <h2 className="text-3xl font-bold text-center mb-4">Everything the OPD Needs</h2>
            <p className="text-center text-slate-500 mb-12 max-w-2xl mx-auto">From reception to dispensing, every step of the patient journey is covered.</p>
            <div className="grid md:grid-cols-3 gap-8">
              <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
                <h3 className="text-xl font-bold mb-4 text-sky-700">Reception & Registration</h3>
                <ul className="space-y-3 text-sm text-slate-600">
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Patient registration with MRN, NRC, and NHIMA capture</li>
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Appointment scheduling and walk-in queue management</li>
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Token printing and department routing</li>
                </ul>
              </div>
              <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
                <h3 className="text-xl font-bold mb-4 text-sky-700">Clinical Workflow</h3>
                <ul className="space-y-3 text-sm text-slate-600">
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Nurse triage and vitals recording</li>
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Doctor SOAP notes and clinical history</li>
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Lab, Radiology, and Pharmacy ordering</li>
                </ul>
              </div>
              <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
                <h3 className="text-xl font-bold mb-4 text-sky-700">Billing & Revenue</h3>
                <ul className="space-y-3 text-sm text-slate-600">
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Auto-generated invoices on visit close</li>
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Cash, Mobile Money, and Insurance claim tracking</li>
                  <li className="flex items-start gap-2"><span className="text-emerald-500 mt-0.5">✓</span> Daily collection and revenue reports</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing in ZMW */}
        <section id="pricing" className="py-24 px-6 max-w-6xl mx-auto text-center bg-white">
          <h2 className="text-3xl font-bold mb-4">Simple, Transparent Pricing</h2>
          <p className="text-slate-500 mb-12">All prices are in Zambian Kwacha (ZMW). No hidden fees.</p>
          <div className="grid md:grid-cols-3 gap-8">
            <PriceCard 
              name="Starter" 
              price="K1,250" 
              period="/mo" 
              annual="K15,000 / year"
              desc="Perfect for small clinics getting started." 
              features={["1 Doctor", "Up to 500 Patients/mo", "OPD & Billing", "Basic Reporting"]} 
            />
            <PriceCard 
              name="Pro" 
              price="K3,500" 
              period="/mo" 
              annual="K42,000 / year"
              desc="For growing clinics with more staff." 
              features={["Up to 5 Doctors", "Unlimited Patients", "Lab & Pharmacy", "SMS Notifications", "Insurance Claims"]} 
              highlighted={true} 
            />
            <PriceCard 
              name="Enterprise" 
              price="Custom" 
              period="" 
              annual=""
              desc="For hospitals and multi-branch groups." 
              features={["Unlimited Doctors", "Multi-Branch", "Dedicated Support", "Custom Integrations", "SLA Guarantee"]} 
            />
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-12 border-t border-slate-800">
        <div className="max-w-6xl mx-auto px-6 grid md:grid-cols-3 gap-8 text-sm">
          <div>
            <div className="text-white text-lg font-bold mb-4">Nimbus OPD Cloud</div>
            <p>© {new Date().getFullYear()} Nimbus Software Ltd. All rights reserved.</p>
            <p className="mt-2">Built for modern healthcare in Zambia.</p>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Legal</h4>
            <ul className="space-y-2">
              <li><button onClick={() => setShowTerms(true)} className="hover:text-white hover:underline text-left">Terms & Conditions</button></li>
              <li><button onClick={() => setShowPrivacy(true)} className="hover:text-white hover:underline text-left">Privacy Policy</button></li>
            </ul>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Contact</h4>
            <ul className="space-y-2">
              <li>support@nimbusopd.com</li>
              <li>+260 211 123 456</li>
              <li>Lusaka, Zambia</li>
            </ul>
          </div>
        </div>
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
                <div className="text-5xl mb-4">⏳</div>
                <h3 className="text-xl font-bold text-amber-600 mb-2">Registration Received</h3>
                <p className="text-slate-600 mb-6 text-sm">
                  Your clinic has been registered. However, your account is currently <b>pending approval and payment</b>. 
                  Our platform team will review your application and contact you shortly.
                </p>
                <Link to="/login" className="bg-slate-200 text-slate-700 px-6 py-2 rounded hover:bg-slate-300 w-full inline-block font-medium">Back to Login</Link>
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
                  <span>
                    I agree to the <button type="button" onClick={() => setShowTerms(true)} className="text-sky-600 hover:underline">Terms & Conditions</button> and <button type="button" onClick={() => setShowPrivacy(true)} className="text-sky-600 hover:underline">Privacy Policy</button>.
                  </span>
                </label>

                <button type="submit" disabled={busy} className="w-full bg-sky-600 text-white py-2 rounded font-bold hover:bg-sky-700 disabled:opacity-50 mt-4">
                  {busy ? "Creating Clinic..." : "Register Clinic"}
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Terms Modal (Same as before) */}
      {showTerms && (
        <div className="fixed inset-0 bg-slate-900/60 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b flex justify-between items-center bg-slate-50 rounded-t-xl">
              <h2 className="text-xl font-bold text-slate-800">Terms & Conditions</h2>
              <button onClick={() => setShowTerms(false)} className="text-slate-400 hover:text-slate-600 text-xl">✕</button>
            </div>
            <div className="p-6 overflow-y-auto text-sm text-slate-600 space-y-4">
              <h3 className="font-bold text-slate-800 text-base">1. Acceptance of Terms</h3>
              <p>By registering for Nimbus OPD Cloud, you agree to these terms. If you are registering on behalf of a clinic, you represent that you have the authority to bind that clinic to these terms.</p>
              <h3 className="font-bold text-slate-800 text-base">2. Subscription and Payment</h3>
              <p>Access to the platform is granted upon approval and receipt of payment. Fees are billed monthly or annually in advance in Zambian Kwacha (ZMW). All fees are non-refundable except as required by law.</p>
              <h3 className="font-bold text-slate-800 text-base">3. Data Protection and HIPAA</h3>
              <p>You are solely responsible for obtaining patient consent and ensuring compliance with local health data regulations. Nimbus provides the technical safeguards (encryption, isolation) but does not act as a covered entity.</p>
              <h3 className="font-bold text-slate-800 text-base">4. Limitation of Liability</h3>
              <p>Nimbus Software Ltd. shall not be liable for any indirect, incidental, or consequential damages arising out of the use or inability to use the service.</p>
            </div>
            <div className="p-4 border-t bg-slate-50 rounded-b-xl flex justify-end">
              <button onClick={() => setShowTerms(false)} className="px-6 py-2 bg-slate-200 text-slate-700 rounded font-medium hover:bg-slate-300">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Privacy Modal (Same as before) */}
      {showPrivacy && (
        <div className="fixed inset-0 bg-slate-900/60 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b flex justify-between items-center bg-slate-50 rounded-t-xl">
              <h2 className="text-xl font-bold text-slate-800">Privacy Policy</h2>
              <button onClick={() => setShowPrivacy(false)} className="text-slate-400 hover:text-slate-600 text-xl">✕</button>
            </div>
            <div className="p-6 overflow-y-auto text-sm text-slate-600 space-y-4">
              <h3 className="font-bold text-slate-800 text-base">1. Information We Collect</h3>
              <p>We collect clinic details, admin user information, and patient data entered by your staff. We also collect usage logs for security and debugging.</p>
              <h3 className="font-bold text-slate-800 text-base">2. How We Use Information</h3>
              <p>Your data is used solely to provide the Nimbus OPD service. We do not sell your data or use it for advertising. Patient data is strictly isolated using PostgreSQL Row-Level Security.</p>
              <h3 className="font-bold text-slate-800 text-base">3. Data Retention</h3>
              <p>We retain your data for as long as your subscription is active. Upon cancellation, you may request a full export of your data.</p>
            </div>
            <div className="p-4 border-t bg-slate-50 rounded-b-xl flex justify-end">
              <button onClick={() => setShowPrivacy(false)} className="px-6 py-2 bg-slate-200 text-slate-700 rounded font-medium hover:bg-slate-300">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PriceCard({ name, price, period, annual, desc, features, highlighted = false }: any) {
  return (
    <div className={`border rounded-2xl p-8 ${highlighted ? 'border-sky-600 shadow-xl relative bg-white transform md:-translate-y-4' : 'border-slate-200 bg-slate-50'}`}>
      {highlighted && <div className="absolute top-0 left-1/2 -translate-x-1/2 bg-sky-600 text-white px-4 py-1 rounded-b-lg text-xs font-bold tracking-wide uppercase">Most Popular</div>}
      <h3 className="text-xl font-bold text-slate-800 mb-2">{name}</h3>
      <div className="text-4xl font-extrabold text-slate-900 mb-1">{price}<span className="text-lg text-slate-500 font-medium">{period}</span></div>
      {annual && <div className="text-sm text-slate-500 mb-4">{annual}</div>}
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

print("==> Done. The landing page has been updated with detailed features and ZMW pricing.")