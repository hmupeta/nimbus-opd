#!/usr/bin/env python3
"""
add_use_cases_page.py
1. Creates a detailed Use Cases documentation page.
2. Wires it into the React Router.
3. Adds links to the Landing Page.
4. Builds and pushes.
"""
import subprocess, sys, shutil, os, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

npm = npm_path()
if not npm:
    sys.exit("npm not found")

# ═════════════════════════════════════════════════════════════════════
# 1. Create the Use Cases Page
# ═════════════════════════════════════════════════════════════════════
print("==> Creating UseCases.tsx...")
usecase_path = SRC / "pages" / "UseCases.tsx"
usecase_path.parent.mkdir(parents=True, exist_ok=True)

USECASE_CONTENT = r'''import { Link } from "react-router-dom";
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
'''

usecase_path.write_text(USECASE_CONTENT, encoding="utf-8")
print(f"   wrote {usecase_path.relative_to(ROOT)}")

# ═════════════════════════════════════════════════════════════════════
# 2. Update Landing Page to link to Use Cases
# ═════════════════════════════════════════════════════════════════════
print("==> Updating LandingPage.tsx to link to Use Cases...")
lp_path = SRC / "pages" / "LandingPage.tsx"
if lp_path.exists():
    txt = lp_path.read_text(encoding="utf-8")
    if 'to="/use-cases"' not in txt and 'href="/use-cases"' not in txt:
        # Add to Desktop Nav
        txt = txt.replace(
            '<nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-600">',
            '<nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-600">\n              <a href="/use-cases" className="hover:text-sky-600 transition font-bold text-sky-700">Use Cases</a>'
        )
        # Add to Footer
        txt = txt.replace(
            '<a href="#" className="hover:text-sky-600">Privacy Policy</a>',
            '<a href="/use-cases" className="hover:text-sky-600 font-medium text-slate-700">Use Cases</a>\n            <a href="#" className="hover:text-sky-600">Privacy Policy</a>'
        )
        # Add button below hero
        txt = txt.replace(
            '<button onClick={() => scrollTo("features")} className="inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition-all">\n                Explore Features\n              </button>',
            '<a href="/use-cases" className="inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition-all">\n                Explore Use Cases\n              </a>'
        )
        lp_path.write_text(txt, encoding="utf-8")
        print("   Added links to LandingPage.tsx")
    else:
        print("   LandingPage already has links.")

# ═════════════════════════════════════════════════════════════════════
# 3. Wire up the Router
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching React Router...")
router_files = [SRC / "App.tsx", SRC / "main.tsx", SRC / "routes.tsx", SRC / "router.tsx"]
patched_router = False

for rf in router_files:
    if not rf.exists(): continue
    txt = rf.read_text(encoding="utf-8")
    
    if 'path="/use-cases"' in txt or 'path="use-cases"' in txt:
        print(f"   Router already has /use-cases in {rf.relative_to(FRONTEND)}")
        patched_router = True
        break

    # Add import
    if "import UseCases" not in txt:
        txt = re.sub(r"(import .*? from .*?\n)", r"\1import UseCases from './pages/UseCases';\n", txt, count=1)

    # Add Route
    if "<Route" in txt:
        # React Router v6 standard
        if '<Route path="/login"' in txt:
            txt = txt.replace('<Route path="/login"', '<Route path="/use-cases" element={<UseCases />} />\n        <Route path="/login"')
            patched_router = True
        elif '<Route path="login"' in txt:
            txt = txt.replace('<Route path="login"', '<Route path="use-cases" element={<UseCases />} />\n        <Route path="login"')
            patched_router = True
        elif '<Route path="/"' in txt:
            txt = txt.replace('<Route path="/"', '<Route path="/use-cases" element={<UseCases />} />\n        <Route path="/"')
            patched_router = True
    
    # React Router createBrowserRouter
    elif "createBrowserRouter" in txt and 'path: "/login"' in txt:
        txt = txt.replace('path: "/login"', 'path: "use-cases", element: <UseCases /> },\n    { path: "/login"')
        patched_router = True

    if patched_router:
        rf.write_text(txt, encoding="utf-8")
        print(f"   Injected route into {rf.relative_to(FRONTEND)}")
        break

if not patched_router:
    print("   [WARN] Could not auto-patch the Router.")
    print("   Please manually add: <Route path=\"/use-cases\" element={<UseCases />} /> to your routes.")

# ═════════════════════════════════════════════════════════════════════
# 4. Build & Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running Vite build...")
env = os.environ.copy()
env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)

if r.returncode == 0:
    print("   ✓ Build succeeded!")
else:
    print("   ❌ Build failed. Here is the error:")
    for line in (r.stdout + r.stderr).splitlines()[-15:]:
        print("     " + line)
    sys.exit(1)

print("\n==> Committing and pushing...")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()

if status:
    subprocess.run(["git", "commit", "-m", "docs: add detailed use cases page and link to landing page"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")

subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. Wait for Render to auto-deploy the frontend.")
print("  2. Check the new page at https://nimbus-frontend-z74i.onrender.com/use-cases")