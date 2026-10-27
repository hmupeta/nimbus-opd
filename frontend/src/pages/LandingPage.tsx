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
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans overflow-x-hidden">
      {/* ─── NAVBAR ─── */}
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between sticky top-0 z-40 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-sky-600 rounded-lg flex items-center justify-center text-white font-bold text-xl shadow-md">N</div>
          <div className="text-2xl font-bold text-slate-800 tracking-tight">Nimbus <span className="text-sky-600">OPD Cloud</span></div>
        </div>
        <div className="space-x-6 hidden md:flex items-center">
          <a href="#features" className="text-slate-600 font-medium hover:text-sky-700 transition">Features</a>
          <a href="#workflow" className="text-slate-600 font-medium hover:text-sky-700 transition">How it Works</a>
          <a href="#pricing" className="text-slate-600 font-medium hover:text-sky-700 transition">Pricing</a>
          <Link to="/login" className="text-slate-600 font-medium hover:text-sky-700 transition">Sign In</Link>
          <button onClick={() => setShowForm(true)} className="bg-sky-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-sky-700 shadow-md transition transform hover:-translate-y-0.5">Get Started</button>
        </div>
      </header>

      <main className="flex-1">
        {/* ─── HERO: PROBLEM VS SOLUTION ─── */}
        <section className="py-20 px-6 max-w-7xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-6">
            <div className="inline-block bg-sky-100 text-sky-800 font-semibold px-4 py-1.5 rounded-full text-sm shadow-sm">
              Built for Zambian Clinics
            </div>
            <h1 className="text-5xl lg:text-6xl font-extrabold text-slate-900 leading-tight">
              Stop Losing Revenue to <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-500 to-orange-500">Paperwork.</span>
            </h1>
            <p className="text-xl text-slate-600">
              Are you still struggling with long OPD queues, manual billing errors, and scattered paper records? It's time to move to a smarter, cloud-based system.
            </p>
            <div className="flex gap-4 pt-4">
              <button onClick={() => setShowForm(true)} className="bg-sky-600 text-white px-8 py-3.5 rounded-lg text-lg font-bold hover:bg-sky-700 shadow-lg transition transform hover:-translate-y-1">
                Register Your Clinic
              </button>
              <a href="#features" className="bg-white text-slate-700 border-2 border-slate-200 px-8 py-3.5 rounded-lg text-lg font-bold hover:bg-slate-50 transition">
                See Features
              </a>
            </div>
          </div>
          <div className="relative">
            <div className="absolute inset-0 bg-sky-200 rounded-3xl transform rotate-3 scale-105 opacity-50"></div>
            <img 
              src="https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&q=80&w=1200" 
              alt="Modern Clinic" 
              className="relative rounded-3xl shadow-2xl object-cover h-[400px] w-full"
            />
            <div className="absolute -bottom-6 -left-6 bg-white p-4 rounded-xl shadow-xl flex items-center gap-3">
              <div className="w-10 h-10 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center text-xl font-bold">✓</div>
              <div>
                <p className="text-sm text-slate-500 font-medium">Patient Wait Time</p>
                <p className="text-lg font-bold text-slate-800">Reduced by 60%</p>
              </div>
            </div>
          </div>
        </section>

        {/* ─── FEATURE HIGHLIGHTS ─── */}
        <section id="features" className="py-24 bg-white border-y border-slate-200">
          <div className="max-w-6xl mx-auto px-6">
            <h2 className="text-4xl font-bold text-center mb-4 text-slate-800">The Power of Nimbus</h2>
            <p className="text-center text-slate-500 mb-16 max-w-2xl mx-auto text-lg">
              Nimbus OPD Cloud automates your entire patient journey—from registration to billing—in one unified, secure platform.
            </p>
            <div className="grid md:grid-cols-3 gap-8">
              <FeatureCard 
                icon="🎫" 
                title="Smart OPD & Queue" 
                desc="Digital token generation, live queue display, and automated patient flow to reduce waiting times."
              />
              <FeatureCard 
                icon="📋" 
                title="Unified EMR/EHR" 
                desc="A complete digital record of every patient visit, including SOAP notes, vitals, and history."
              />
              <FeatureCard 
                icon="💊" 
                title="Integrated Pharmacy" 
                desc="Barcode-based inventory with automatic expiry alerts and seamless billing integration."
              />
              <FeatureCard 
                icon="🔬" 
                title="Connected Lab & Radiology" 
                desc="Order tests digitally, receive results directly into the patient's EMR, and track turnaround times."
              />
              <FeatureCard 
                icon="💳" 
                title="Automated Billing" 
                desc="Zero-error invoices, support for Mobile Money, Stripe/PayPal, and insurance claims."
              />
              <FeatureCard 
                icon="📊" 
                title="Real-Time Analytics" 
                desc="Dashboards for revenue, doctor performance, patient footfall, and lab TAT."
              />
            </div>
          </div>
        </section>

        {/* ─── WORKFLOW ─── */}
        <section id="workflow" className="py-24 bg-slate-50">
          <div className="max-w-6xl mx-auto px-6">
            <h2 className="text-4xl font-bold text-center mb-16 text-slate-800">How Nimbus Works</h2>
            <div className="grid md:grid-cols-4 gap-8">
              <WorkflowStep 
                num="1" 
                title="Register" 
                desc="A receptionist registers a patient and generates a digital token."
              />
              <WorkflowStep 
                num="2" 
                title="Triage" 
                desc="A nurse records vitals, which automatically updates the patient's EMR."
              />
              <WorkflowStep 
                num="3" 
                title="Consult" 
                desc="The doctor reviews history, writes digital prescriptions, and orders labs."
              />
              <WorkflowStep 
                num="4" 
                title="Bill" 
                desc="An invoice is auto-generated, pharmacy dispenses, and payment is collected."
              />
            </div>
          </div>
        </section>

        {/* ─── BENEFITS ─── */}
        <section className="py-24 bg-sky-900 text-white">
          <div className="max-w-6xl mx-auto px-6 text-center">
            <h2 className="text-4xl font-bold mb-16">Why Clinics Choose Nimbus</h2>
            <div className="grid md:grid-cols-4 gap-8">
              <div>
                <p className="text-5xl font-extrabold text-sky-400 mb-2">60%</p>
                <p className="text-lg font-medium">Faster patient throughput</p>
              </div>
              <div>
                <p className="text-5xl font-extrabold text-emerald-400 mb-2">22%</p>
                <p className="text-lg font-medium">Revenue leakage prevented</p>
              </div>
              <div>
                <p className="text-5xl font-extrabold text-indigo-400 mb-2">100%</p>
                <p className="text-lg font-medium">Compliance with audit trails</p>
              </div>
              <div>
                <p className="text-5xl font-extrabold text-amber-400 mb-2">24/7</p>
                <p className="text-lg font-medium">Access from any device</p>
              </div>
            </div>
          </div>
        </section>

        {/* ─── PRICING ─── */}
        <section id="pricing" className="py-24 px-6 max-w-6xl mx-auto text-center bg-slate-50">
          <h2 className="text-4xl font-bold mb-4 text-slate-800">Simple, Transparent Pricing</h2>
          <p className="text-slate-500 mb-16 text-lg">All prices are in Zambian Kwacha (ZMW). No hidden fees.</p>
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

      {/* ─── FOOTER ─── */}
      <footer className="bg-slate-900 text-slate-400 py-12 border-t border-slate-800">
        <div className="max-w-6xl mx-auto px-6 grid md:grid-cols-3 gap-8 text-sm">
          <div>
            <div className="text-white text-lg font-bold mb-4 flex items-center gap-2">
              <div className="w-6 h-6 bg-sky-600 rounded flex items-center justify-center text-xs">N</div>
              Nimbus OPD Cloud
            </div>
            <p>© {new Date().getFullYear()} Nimbus Software Ltd. All rights reserved.</p>
            <p className="mt-2">Built for modern healthcare in Zambia.</p>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Legal</h4>
            <ul className="space-y-2">
              <li><button onClick={() => setShowTerms(true)} className="hover:text-white hover:underline text-left transition">Terms & Conditions</button></li>
              <li><button onClick={() => setShowPrivacy(true)} className="hover:text-white hover:underline text-left transition">Privacy Policy</button></li>
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

      {/* ─── REGISTRATION MODAL ─── */}
      {showForm && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-slate-800">Register Clinic</h2>
              <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">&times;</button>
            </div>
            
            {success ? (
              <div className="text-center py-8">
                <div className="text-6xl mb-4">⏳</div>
                <h3 className="text-xl font-bold text-amber-600 mb-2">Registration Received</h3>
                <p className="text-slate-600 mb-6 text-sm">
                  Your clinic has been registered. However, your account is currently <b>pending approval and payment</b>. 
                  Our platform team will review your application and contact you shortly.
                </p>
                <Link to="/login" className="bg-slate-200 text-slate-700 px-6 py-2 rounded-lg hover:bg-slate-300 w-full inline-block font-medium transition">Back to Login</Link>
              </div>
            ) : (
              <form onSubmit={onRegister} className="space-y-4">
                {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg border border-red-100">{error}</div>}
                
                <div className="grid grid-cols-2 gap-4">
                  <label className="block text-sm">
                    <span className="text-slate-600 font-medium">Clinic Name</span>
                    <input name="clinic_name" required placeholder="City Health" className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-sky-500 outline-none" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-slate-600 font-medium">Short Code</span>
                    <input name="clinic_code" required placeholder="city-health" className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-sky-500 outline-none" />
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <label className="block text-sm">
                    <span className="text-slate-600 font-medium">First Name</span>
                    <input name="first_name" required placeholder="John" className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-sky-500 outline-none" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-slate-600 font-medium">Last Name</span>
                    <input name="last_name" required placeholder="Doe" className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-sky-500 outline-none" />
                  </label>
                </div>

                <label className="block text-sm">
                  <span className="text-slate-600 font-medium">Admin Email</span>
                  <input type="email" name="email" required placeholder="admin@cityhealth.com" className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-sky-500 outline-none" />
                </label>

                <label className="block text-sm">
                  <span className="text-slate-600 font-medium">Password</span>
                  <input type="password" name="password" required minLength={6} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-sky-500 outline-none" />
                </label>

                <label className="flex items-start gap-2 text-sm text-slate-600 mt-2">
                  <input type="checkbox" required className="mt-1 rounded border-slate-300 text-sky-600 focus:ring-sky-500" />
                  <span>
                    I agree to the <button type="button" onClick={() => setShowTerms(true)} className="text-sky-600 hover:underline font-medium">Terms & Conditions</button> and <button type="button" onClick={() => setShowPrivacy(true)} className="text-sky-600 hover:underline font-medium">Privacy Policy</button>.
                  </span>
                </label>

                <button type="submit" disabled={busy} className="w-full bg-sky-600 text-white py-2.5 rounded-lg font-bold hover:bg-sky-700 disabled:opacity-50 mt-4 transition shadow-md">
                  {busy ? "Creating Clinic..." : "Register Clinic"}
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ─── TERMS MODAL ─── */}
      {showTerms && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b flex justify-between items-center bg-slate-50 rounded-t-2xl">
              <h2 className="text-xl font-bold text-slate-800">Terms & Conditions</h2>
              <button onClick={() => setShowTerms(false)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">&times;</button>
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
            <div className="p-4 border-t bg-slate-50 rounded-b-2xl flex justify-end">
              <button onClick={() => setShowTerms(false)} className="px-6 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300 transition">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* ─── PRIVACY MODAL ─── */}
      {showPrivacy && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b flex justify-between items-center bg-slate-50 rounded-t-2xl">
              <h2 className="text-xl font-bold text-slate-800">Privacy Policy</h2>
              <button onClick={() => setShowPrivacy(false)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">&times;</button>
            </div>
            <div className="p-6 overflow-y-auto text-sm text-slate-600 space-y-4">
              <h3 className="font-bold text-slate-800 text-base">1. Information We Collect</h3>
              <p>We collect clinic details, admin user information, and patient data entered by your staff. We also collect usage logs for security and debugging.</p>
              <h3 className="font-bold text-slate-800 text-base">2. How We Use Information</h3>
              <p>Your data is used solely to provide the Nimbus OPD service. We do not sell your data or use it for advertising. Patient data is strictly isolated using PostgreSQL Row-Level Security.</p>
              <h3 className="font-bold text-slate-800 text-base">3. Data Retention</h3>
              <p>We retain your data for as long as your subscription is active. Upon cancellation, you may request a full export of your data.</p>
            </div>
            <div className="p-4 border-t bg-slate-50 rounded-b-2xl flex justify-end">
              <button onClick={() => setShowPrivacy(false)} className="px-6 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300 transition">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── HELPER COMPONENTS ───

function FeatureCard({ icon, title, desc }: { icon: string, title: string, desc: string }) {
  return (
    <div className="bg-slate-50 p-8 rounded-2xl border border-slate-200 hover:shadow-lg transition duration-300 transform hover:-translate-y-1">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-xl font-bold mb-2 text-slate-800">{title}</h3>
      <p className="text-slate-600 text-sm leading-relaxed">{desc}</p>
    </div>
  );
}

function WorkflowStep({ num, title, desc }: { num: string, title: string, desc: string }) {
  return (
    <div className="relative text-center">
      <div className="w-16 h-16 bg-sky-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4 shadow-lg border-4 border-sky-200">
        {num}
      </div>
      <h3 className="text-lg font-bold mb-2 text-slate-800">{title}</h3>
      <p className="text-slate-600 text-sm leading-relaxed">{desc}</p>
    </div>
  );
}

function PriceCard({ name, price, period, annual, desc, features, highlighted = false }: any) {
  return (
    <div className={`border rounded-3xl p-8 flex flex-col ${highlighted ? 'border-sky-600 shadow-2xl relative bg-white transform md:-translate-y-4' : 'border-slate-200 bg-white'}`}>
      {highlighted && <div className="absolute top-0 left-1/2 -translate-x-1/2 bg-sky-600 text-white px-4 py-1 rounded-b-lg text-xs font-bold tracking-wide uppercase shadow-sm">Most Popular</div>}
      <h3 className="text-xl font-bold text-slate-800 mb-2">{name}</h3>
      <div className="text-4xl font-extrabold text-slate-900 mb-1">{price}<span className="text-lg text-slate-500 font-medium">{period}</span></div>
      {annual && <div className="text-sm text-slate-500 mb-4 font-medium bg-slate-100 w-fit px-2 py-1 rounded">{annual}</div>}
      <p className="text-slate-500 mb-6 text-sm flex-1">{desc}</p>
      <ul className="space-y-3 mb-8 text-left text-sm">
        {features.map((f: string) => (
          <li key={f} className="flex items-center gap-2 text-slate-700">
            <span className="text-emerald-500 font-bold">✓</span> {f}
          </li>
        ))}
      </ul>
      <button className={`w-full py-2.5 rounded-xl font-bold transition ${highlighted ? 'bg-sky-600 text-white hover:bg-sky-700 shadow-md' : 'border-2 border-slate-300 text-slate-700 hover:bg-slate-50'}`}>
        Choose {name}
      </button>
    </div>
  );
}