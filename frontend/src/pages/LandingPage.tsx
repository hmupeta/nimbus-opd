import React, { useState } from "react";
import { 
  ShieldCheck, HeartPulse, Stethoscope, 
  Smartphone, CreditCard, MessageSquare, 
  FileCheck, BarChart3, Users, 
  CheckCircle2, ArrowRight, Menu, X 
} from "lucide-react";

export default function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    setMobileMenuOpen(false);
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 selection:bg-sky-200">
      
      {/* ── NAVBAR ────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => window.scrollTo(0,0)}>
              <div className="bg-sky-600 p-2 rounded-lg">
                <HeartPulse className="h-5 w-5 text-white" />
              </div>
              <span className="text-xl font-bold text-slate-900 tracking-tight">Nimbus OPD</span>
            </div>
            
            <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-600">
              <button onClick={() => scrollTo("features")} className="hover:text-sky-600 transition">Features</button>
              <button onClick={() => scrollTo("integrations")} className="hover:text-sky-600 transition">Integrations</button>
              <button onClick={() => scrollTo("insurance")} className="hover:text-sky-600 transition">Insurance & NHIMA</button>
              <button onClick={() => scrollTo("pricing")} className="hover:text-sky-600 transition">Pricing</button>
            </nav>

            <div className="hidden md:flex items-center gap-4">
              <a href="/login" className="text-sm font-medium text-slate-700 hover:text-sky-600">Log in</a>
              <a href="/login" className="bg-sky-600 hover:bg-sky-700 text-white px-5 py-2 rounded-lg text-sm font-medium transition shadow-sm">
                Book a Demo
              </a>
            </div>

            <button className="md:hidden p-2" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
        {/* Mobile Nav */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-white border-t border-slate-100 p-4 space-y-3 shadow-lg">
            <button onClick={() => scrollTo("features")} className="block w-full text-left py-2 text-slate-600 font-medium">Features</button>
            <button onClick={() => scrollTo("integrations")} className="block w-full text-left py-2 text-slate-600 font-medium">Integrations</button>
            <button onClick={() => scrollTo("insurance")} className="block w-full text-left py-2 text-slate-600 font-medium">Insurance & NHIMA</button>
            <hr className="border-slate-100" />
            <a href="/login" className="block w-full text-center bg-sky-600 text-white py-2 rounded-lg font-medium">Log in</a>
          </div>
        )}
      </header>

      {/* ── HERO SECTION ───────────────────────────────────────────── */}
      <section className="relative pt-20 pb-32 overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?ixlib=rb-4.0.3&auto=format&fit=crop&w=2000&q=80')] bg-cover bg-center opacity-5"></div>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="text-center max-w-3xl mx-auto">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-100 text-sky-700 text-xs font-semibold mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
              </span>
              Built for the Zambian Healthcare Market
            </div>
            <h1 className="text-4xl md:text-6xl font-extrabold text-slate-900 tracking-tight mb-6 leading-tight">
              The Modern OPD Software that <span className="text-sky-600">Connects</span> Your Clinic.
            </h1>
            <p className="text-lg md:text-xl text-slate-600 mb-10 max-w-2xl mx-auto">
              Streamline patient queues, integrate Mobile Money & Card payments, automate SMS/WhatsApp reminders, and process NHIMA insurance claims—all from one secure platform.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <a href="/login" className="inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-white bg-sky-600 rounded-xl hover:bg-sky-700 shadow-lg shadow-sky-600/20 transition-all hover:-translate-y-0.5">
                Start Free Trial <ArrowRight className="ml-2 h-5 w-5" />
              </a>
              <button onClick={() => scrollTo("features")} className="inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition-all">
                Explore Features
              </button>
            </div>
            <p className="mt-4 text-sm text-slate-500">No credit card required. 14-day free trial.</p>
          </div>
        </div>
      </section>

      {/* ── TRUST STATS ───────────────────────────────────────────── */}
      <section className="border-y border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <p className="text-3xl font-extrabold text-slate-900">99.9%</p>
              <p className="text-sm text-slate-500 font-medium mt-1">Uptime Reliability</p>
            </div>
            <div>
              <p className="text-3xl font-extrabold text-slate-900">15 min</p>
              <p className="text-sm text-slate-500 font-medium mt-1">Average Wait Time Reduction</p>
            </div>
            <div>
              <p className="text-3xl font-extrabold text-slate-900">3+</p>
              <p className="text-sm text-slate-500 font-medium mt-1">Mobile Money Networks</p>
            </div>
            <div>
              <p className="text-3xl font-extrabold text-slate-900">100%</p>
              <p className="text-sm text-slate-500 font-medium mt-1">NHIMA Claim Ready</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── CORE FEATURES ─────────────────────────────────────────── */}
      <section id="features" className="py-24 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">Everything your clinic needs. <br/>Nothing you don't.</h2>
            <p className="text-lg text-slate-600">A complete OPD ecosystem designed to eliminate paperwork, reduce queues, and increase revenue.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 hover:shadow-md transition">
              <div className="bg-blue-50 w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Smart Queue Management</h3>
              <p className="text-slate-600 text-sm leading-relaxed">Digital token generation, live queue tracking, and automated triage. Reduce waiting room congestion and improve patient satisfaction.</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 hover:shadow-md transition">
              <div className="bg-emerald-50 w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                <Stethoscope className="h-6 w-6 text-emerald-600" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Clinical & E-Prescriptions</h3>
              <p className="text-slate-600 text-sm leading-relaxed">Digital patient records, vitals tracking, and instant e-prescriptions sent directly to your pharmacy or the patient's phone.</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 hover:shadow-md transition">
              <div className="bg-purple-50 w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                <BarChart3 className="h-6 w-6 text-purple-600" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Financial & Revenue Reports</h3>
              <p className="text-slate-600 text-sm leading-relaxed">Real-time Profit & Loss, Balance Sheets, AR Aging, and Cash Flow statements. Make data-driven decisions instantly.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── INTEGRATIONS (PAYMENTS & COMMS) ───────────────────────── */}
      <section id="integrations" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-6">Seamless Payments. <br/>Instant Communication.</h2>
              <p className="text-lg text-slate-600 mb-8">Nimbus OPD connects directly to the tools your patients already use. No more manual reconciliation or missed appointments.</p>
              
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="flex-shrink-0 mt-1">
                    <div className="bg-amber-100 p-2 rounded-lg"><Smartphone className="h-5 w-5 text-amber-600" /></div>
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900">Mobile Money Integration</h4>
                    <p className="text-sm text-slate-600 mt-1">Accept instant payments via <strong>MTN MoMo, Airtel Money, and Zamtel Kwacha</strong>. Automatic receipt generation and ledger posting.</p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="flex-shrink-0 mt-1">
                    <div className="bg-indigo-100 p-2 rounded-lg"><CreditCard className="h-5 w-5 text-indigo-600" /></div>
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900">Card Payments (Stripe & PayPal)</h4>
                    <p className="text-sm text-slate-600 mt-1">Securely process international and local card payments. PCI-DSS compliant and fully integrated with your billing module.</p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="flex-shrink-0 mt-1">
                    <div className="bg-emerald-100 p-2 rounded-lg"><MessageSquare className="h-5 w-5 text-emerald-600" /></div>
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900">SMS & WhatsApp Notifications</h4>
                    <p className="text-sm text-slate-600 mt-1">Automated appointment reminders, lab result alerts, and payment confirmations sent via SMS or WhatsApp to reduce no-shows.</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-tr from-sky-100 to-emerald-50 rounded-3xl transform rotate-3 scale-105 -z-10"></div>
              <div className="bg-white p-8 rounded-2xl shadow-xl border border-slate-200">
                <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-red-400"></div>
                    <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                    <div className="w-3 h-3 rounded-full bg-emerald-400"></div>
                  </div>
                  <span className="text-xs font-mono text-slate-400">payment_gateway.config</span>
                </div>
                <div className="space-y-3 font-mono text-sm">
                  <div className="flex justify-between items-center p-3 bg-slate-50 rounded border border-slate-100">
                    <span className="text-slate-700">MTN Mobile Money</span>
                    <span className="text-emerald-600 font-bold">Active</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-slate-50 rounded border border-slate-100">
                    <span className="text-slate-700">Airtel Money</span>
                    <span className="text-emerald-600 font-bold">Active</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-slate-50 rounded border border-slate-100">
                    <span className="text-slate-700">Stripe (Cards)</span>
                    <span className="text-emerald-600 font-bold">Active</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-slate-50 rounded border border-slate-100">
                    <span className="text-slate-700">WhatsApp API</span>
                    <span className="text-emerald-600 font-bold">Connected</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── INSURANCE & NHIMA SECTION ─────────────────────────────── */}
      <section id="insurance" className="py-24 bg-slate-900 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-900/50 border border-sky-700 text-sky-300 text-xs font-semibold mb-6">
                <ShieldCheck className="h-4 w-4" /> NHIMA Ready
              </div>
              <h2 className="text-3xl md:text-4xl font-bold mb-6">Simplify Insurance Claims. <br/>Eliminate Denials.</h2>
              <p className="text-lg text-slate-300 mb-8">
                Manual insurance claims are slow and error-prone. Nimbus OPD is built to integrate with <strong>NHIMA</strong> and private insurance providers to verify eligibility, submit claims, and track payments in real-time.
              </p>
              <ul className="space-y-4">
                {[
                  "Real-time patient eligibility verification",
                  "Automated claim submission (FHIR & REST APIs)",
                  "Co-payment and deductible management",
                  "Reduced claim denial rates"
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-sky-400 flex-shrink-0 mt-0.5" />
                    <span className="text-slate-200">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700">
               <div className="flex items-center gap-4 mb-6">
                 <div className="bg-sky-500/20 p-3 rounded-full"><FileCheck className="h-6 w-6 text-sky-400" /></div>
                 <div>
                   <h4 className="font-bold text-white">NHIMA Claim Status</h4>
                   <p className="text-xs text-slate-400">Ref: CLM-2026-8942</p>
                 </div>
               </div>
               <div className="space-y-4">
                 <div className="flex justify-between text-sm border-b border-slate-700 pb-2">
                   <span className="text-slate-400">Eligibility Check</span>
                   <span className="text-emerald-400 font-medium">Verified ✓</span>
                 </div>
                 <div className="flex justify-between text-sm border-b border-slate-700 pb-2">
                   <span className="text-slate-400">Claim Submitted</span>
                   <span className="text-sky-400 font-medium">Processing</span>
                 </div>
                 <div className="flex justify-between text-sm border-b border-slate-700 pb-2">
                   <span className="text-slate-400">Expected Reimbursement</span>
                   <span className="text-white font-medium">ZMW 1,250.00</span>
                 </div>
               </div>
               <div className="mt-6 p-3 bg-sky-900/30 rounded-lg text-xs text-sky-300 border border-sky-800">
                 💡 Did you know? Clinics using automated NHIMA verification reduce claim denials by up to 40%.
               </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA SECTION ───────────────────────────────────────────── */}
      <section className="py-24 bg-sky-600">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">Ready to modernize your clinic?</h2>
          <p className="text-lg text-sky-100 mb-10 max-w-2xl mx-auto">Join the healthcare providers using Nimbus OPD to save time, reduce costs, and deliver a better patient experience.</p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <a href="/login" className="inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-sky-700 bg-white rounded-xl hover:bg-slate-50 transition-all shadow-lg">
              Get Started for Free
            </a>
            <a href="mailto:sales@nimbusopd.com" className="inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-white border border-sky-400 rounded-xl hover:bg-sky-700 transition-all">
              Contact Sales
            </a>
          </div>
        </div>
      </section>

      {/* ── FOOTER ────────────────────────────────────────────────── */}
      <footer className="bg-slate-50 py-12 border-t border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <HeartPulse className="h-6 w-6 text-sky-600" />
            <span className="text-xl font-bold text-slate-900">Nimbus OPD</span>
          </div>
          <p className="text-sm text-slate-500">© {new Date().getFullYear()} Nimbus OPD. All rights reserved.</p>
          <div className="flex gap-4 text-sm text-slate-500">
            <a href="#" className="hover:text-sky-600">Privacy Policy</a>
            <a href="#" className="hover:text-sky-600">Terms of Service</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
