import { Link } from "react-router-dom";
import { 
  ArrowLeft, Stethoscope, Activity, Users, 
  CreditCard, ShieldCheck, FileText, CheckCircle2,
  Lock, MessageSquare, ArrowRightCircle, Database
} from "lucide-react";

export default function UseCases() {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      {/* Navbar */}
      <header className="sticky top-0 z-50 bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-slate-600 hover:text-sky-600 transition">
            <ArrowLeft className="h-5 w-5" />
            <span className="font-medium">Back to Home</span>
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-slate-900 tracking-tight">Nimbus OPD</span>
            <span className="bg-sky-100 text-sky-700 text-xs font-bold px-2 py-1 rounded">Docs</span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero */}
        <div className="mb-16">
          <h1 className="text-4xl font-extrabold text-slate-900 mb-4">System Capabilities & Use Cases</h1>
          <p className="text-xl text-slate-600 max-w-3xl">
            A comprehensive breakdown of the workflows, security features, and financial controls built into Nimbus OPD to run your clinic efficiently.
          </p>
        </div>

        {/* Section 1: Clinical Flow */}
        <section className="mb-16">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-emerald-100 p-2 rounded-lg"><Stethoscope className="h-6 w-6 text-emerald-600" /></div>
            <h2 className="text-2xl font-bold text-slate-900">1. The Patient Journey (Clinical)</h2>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="divide-y divide-slate-100">
              <div className="p-6 flex gap-4 hover:bg-slate-50 transition">
                <Users className="h-6 w-6 text-slate-400 shrink-0 mt-1" />
                <div>
                  <h4 className="font-bold text-lg text-slate-900">Registration & Demographics</h4>
                  <p className="text-slate-600 mt-1">Receptionists can register new patients, capture demographics, and assign them a unique medical record number (MRN) isolated to your specific clinic tenant.</p>
                </div>
              </div>
              <div className="p-6 flex gap-4 hover:bg-slate-50 transition">
                <Activity className="h-6 w-6 text-slate-400 shrink-0 mt-1" />
                <div>
                  <h4 className="font-bold text-lg text-slate-900">Triage & Vitals</h4>
                  <p className="text-slate-600 mt-1">Nurses record vitals (BP, temp, weight) and generate a digital queue token. The system tracks patient status (Open, Triaged, In Consultation) to eliminate waiting room bottlenecks.</p>
                </div>
              </div>
              <div className="p-6 flex gap-4 hover:bg-slate-50 transition">
                <FileText className="h-6 w-6 text-slate-400 shrink-0 mt-1" />
                <div>
                  <h4 className="font-bold text-lg text-slate-900">Consultation & E-Prescriptions</h4>
                  <p className="text-slate-600 mt-1">Doctors review vitals, input clinical notes, and generate digital prescriptions. Orders for Labs or Radiology are sent directly to the respective departments.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 2: Financial Controls */}
        <section className="mb-16">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-sky-100 p-2 rounded-lg"><CreditCard className="h-6 w-6 text-sky-600" /></div>
            <h2 className="text-2xl font-bold text-slate-900">2. Financial Controls & Billing</h2>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
              <h4 className="font-bold text-lg text-slate-900 mb-2 flex items-center gap-2">
                <Lock className="h-5 w-5 text-red-500" /> Maker-Checker Workflow
              </h4>
              <p className="text-slate-600 text-sm leading-relaxed mb-4">
                Strict financial controls prevent fraud. 
              </p>
              <ul className="text-sm text-slate-600 space-y-2">
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> <strong>Accountants</strong> initiate payments and journal entries.</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> <strong>Finance Managers</strong> review and approve/reject entries.</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Self-approval is automatically blocked by the system.</li>
              </ul>
            </div>
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
              <h4 className="font-bold text-lg text-slate-900 mb-2 flex items-center gap-2">
                <Database className="h-5 w-5 text-blue-500" /> General Ledger & Reporting
              </h4>
              <p className="text-slate-600 text-sm leading-relaxed mb-4">
                A full double-entry accounting system built-in.
              </p>
              <ul className="text-sm text-slate-600 space-y-2">
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Real-time Trial Balance & Journal Entries.</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Automated P&L, Balance Sheet, and Cash Flow.</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> AR Aging and Accounts Payable tracking.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Section 3: Administration */}
        <section className="mb-16">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-purple-100 p-2 rounded-lg"><ShieldCheck className="h-6 w-6 text-purple-600" /></div>
            <h2 className="text-2xl font-bold text-slate-900">3. Administration & Security</h2>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="divide-y divide-slate-100">
              <div className="p-6 flex gap-4 hover:bg-slate-50 transition">
                <Users className="h-6 w-6 text-slate-400 shrink-0 mt-1" />
                <div>
                  <h4 className="font-bold text-lg text-slate-900">Role-Based Access Control (RBAC)</h4>
                  <p className="text-slate-600 mt-1">Assign specific roles (Doctor, Nurse, Accountant, Finance Manager). The system automatically restricts what data and pages each role can access.</p>
                </div>
              </div>
              <div className="p-6 flex gap-4 hover:bg-slate-50 transition">
                <Database className="h-6 w-6 text-slate-400 shrink-0 mt-1" />
                <div>
                  <h4 className="font-bold text-lg text-slate-900">Multi-Tenant Isolation</h4>
                  <p className="text-slate-600 mt-1">All data (patients, invoices, users) is strictly bound to the clinic (tenant). Users created by an Admin automatically inherit that clinic's scope and cannot access data from other clinics.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 4: Integrations */}
        <section>
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-amber-100 p-2 rounded-lg"><MessageSquare className="h-6 w-6 text-amber-600" /></div>
            <h2 className="text-2xl font-bold text-slate-900">4. Payments & Communication</h2>
          </div>
          <div className="bg-sky-50 rounded-2xl border border-sky-100 p-8">
            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <h4 className="font-bold text-lg text-slate-900 mb-3">Mobile Money & Cards</h4>
                <p className="text-slate-600 text-sm mb-4">
                  Built to handle the Zambian market out of the box.
                </p>
                <ul className="space-y-2 text-sm text-slate-700 font-medium">
                  <li>• MTN MoMo & Airtel Money APIs</li>
                  <li>• Stripe & PayPal for international cards</li>
                  <li>• Auto-reconciliation to the General Ledger</li>
                </ul>
              </div>
              <div>
                <h4 className="font-bold text-lg text-slate-900 mb-3">SMS & WhatsApp</h4>
                <p className="text-slate-600 text-sm mb-4">
                  Keep patients engaged and reduce no-shows.
                </p>
                <ul className="space-y-2 text-sm text-slate-700 font-medium">
                  <li>• Automated appointment reminders</li>
                  <li>• Lab result readiness notifications</li>
                  <li>• Payment receipts sent instantly</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <div className="mt-16 text-center">
          <Link to="/login" className="inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-white bg-sky-600 rounded-xl hover:bg-sky-700 transition-all shadow-lg">
            Experience it yourself <ArrowRightCircle className="ml-2 h-5 w-5" />
          </Link>
        </div>
      </main>
    </div>
  );
}
