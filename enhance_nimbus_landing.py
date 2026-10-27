#!/usr/bin/env python3
"""
enhance_nimbus_landing.py -- Rebrand to Nimbus OPD Cloud, add About, T&Cs, and Privacy.
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

print("==> Rebuilding LandingPage.tsx with Nimbus branding, About, and Legal Modals")
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
          <a href="#about" className="text-slate-600 font-medium hover:text-sky-700">About</a>
          <a href="#pricing" className="text-slate-600 font-medium hover:text-sky-700">Pricing</a>
          <Link to="/login" className="text-slate-600 font-medium hover:text-sky-700">Sign In</Link>
          <button onClick={() => setShowForm(true)} className="bg-sky-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-sky-700 shadow-sm transition">Get Started</button>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="py-24 px-6 text-center max-w-5xl mx-auto">
          <div className="inline-block bg-sky-100 text-sky-800 font-semibold px-4 py-1.5 rounded-full text-sm mb-6 shadow-sm">
            The Future of Clinic Management
          </div>
          <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 leading-tight mb-6">
            Run your clinic from the <span className="text-transparent bg-clip-text bg-gradient-to-r from-sky-600 to-indigo-600">cloud</span>.
          </h1>
          <p className="text-xl text-slate-600 mb-10 max-w-2xl mx-auto">
            Nimbus OPD Cloud is a secure, multi-tenant platform that streamlines patient registration, triage, lab requests, pharmacy dispensing, and billing.
          </p>
          <button onClick={() => setShowForm(true)} className="bg-sky-600 text-white px-8 py-4 rounded-lg text-lg font-bold hover:bg-sky-700 shadow-lg transition transform hover:-translate-y-1">
            Register Your Clinic Today
          </button>
        </section>

        {/* Features */}
        <section id="features" className="py-20 bg-white border-y border-slate-200">
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

        {/* About Section */}
        <section id="about" className="py-24 bg-slate-50">
          <div className="max-w-5xl mx-auto px-6 grid md:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl font-bold text-slate-900 mb-6">About Nimbus OPD Cloud</h2>
              <p className="text-lg text-slate-600 mb-4">
                We built Nimbus because we saw clinics struggling with fragmented systems, paper records, and disconnected billing.
              </p>
              <p className="text-lg text-slate-600 mb-4">
                Our mission is to give every clinic—from a single-doctor practice to a multi-branch hospital—the same enterprise-grade software used by large hospitals, without the massive IT overhead.
              </p>
              <p className="text-lg text-slate-600">
                Backed by PostgreSQL Row-Level Security, Nimbus guarantees that your data is mathematically isolated from every other clinic on the platform.
              </p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-xl border border-slate-100 flex items-center justify-center">
              <div className="text-center">
                <div className="text-6xl mb-4">☁️</div>
                <h3 className="text-2xl font-bold text-slate-800">100% Cloud Native</h3>
                <p className="text-slate-500 mt-2">Accessible from any device, anywhere.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section id="pricing" className="py-24 px-6 max-w-6xl mx-auto text-center border-t border-slate-200 bg-white">
          <h2 className="text-3xl font-bold mb-12">Simple, Transparent Pricing</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <PriceCard name="Basic" price="$49" desc="Perfect for small practices." features={["1 Doctor", "Up to 500 Patients/mo", "Basic Reporting"]} />
            <PriceCard name="Pro" price="$99" desc="For growing clinics." features={["Up to 5 Doctors", "Unlimited Patients", "SMS Notifications", "Insurance Claims"]} highlighted={true} />
            <PriceCard name="Enterprise" price="Custom" desc="For hospitals and chains." features={["Unlimited Doctors", "Multi-Branch", "Dedicated Support", "Custom Integrations"]} />
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-12 border-t border-slate-800">
        <div className="max-w-6xl mx-auto px-6 grid md:grid-cols-3 gap-8 text-sm">
          <div>
            <div className="text-white text-lg font-bold mb-4">Nimbus OPD Cloud</div>
            <p>© {new Date().getFullYear()} Nimbus Software Ltd. All rights reserved.</p>
            <p className="mt-2">Built for modern healthcare.</p>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Legal</h4>
            <ul className="space-y-2">
              <li><button onClick={() => setShowTerms(true)} className="hover:text-white hover:underline text-left">Terms & Conditions</button></li>
              <li><button onClick={() => setShowPrivacy(true)} className="hover:text-white hover:underline text-left">Privacy Policy</button></li>
              <li><a href="#" className="hover:text-white hover:underline">Data Processing Agreement</a></li>
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

      {/* Terms Modal */}
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
              <p>Access to the platform is granted upon approval and receipt of payment. Fees are billed monthly or annually in advance. All fees are non-refundable except as required by law.</p>
              
              <h3 className="font-bold text-slate-800 text-base">3. Data Protection and HIPAA</h3>
              <p>You are solely responsible for obtaining patient consent and ensuring compliance with local health data regulations. Nimbus provides the technical safeguards (encryption, isolation) but does not act as a covered entity.</p>
              
              <h3 className="font-bold text-slate-800 text-base">4. Limitation of Liability</h3>
              <p>Nimbus Software Ltd. shall not be liable for any indirect, incidental, or consequential damages arising out of the use or inability to use the service.</p>
              
              <h3 className="font-bold text-slate-800 text-base">5. Termination</h3>
              <p>We reserve the right to suspend or terminate accounts that violate these terms or fail to pay applicable fees.</p>
            </div>
            <div className="p-4 border-t bg-slate-50 rounded-b-xl flex justify-end">
              <button onClick={() => setShowTerms(false)} className="px-6 py-2 bg-slate-200 text-slate-700 rounded font-medium hover:bg-slate-300">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Privacy Modal */}
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
              
              <h3 className="font-bold text-slate-800 text-base">4. Security</h3>
              <p>We use industry-standard encryption at rest and in transit (TLS). All passwords are hashed using PBKDF2.</p>
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

print("==> Done. The landing page has been fully enhanced.")