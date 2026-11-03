#!/usr/bin/env python3
"""
restore_original_integrations.py
1. Uses Git to restore the original Integrations.tsx (with Mobile Money & Stripe).
2. Safely injects the SMS and WhatsApp fields into the restored file.
3. Builds and pushes.
"""
import subprocess, sys, shutil, os, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

# ═════════════════════════════════════════════════════════════════════
# 1. Restore the original file using Git
# ═════════════════════════════════════════════════════════════════════
print("==> Finding and restoring your original Integrations.tsx from Git history...")
# Find the commit where we overwrote the file
log = subprocess.run(["git", "log", "--format=%H %s", "--", "frontend/src/pages/Integrations.tsx"], capture_output=True, text=True).stdout
lines = log.strip().split('\n')
target_commit = None

for i, line in enumerate(lines):
    if 'feat: add integrations settings UI and DB storage' in line:
        if i + 1 < len(lines):
            target_commit = lines[i+1].split()[0]
        break

fe_path = FRONTEND / "src" / "pages" / "Integrations.tsx"
if target_commit:
    subprocess.run(["git", "checkout", target_commit, "--", "frontend/src/pages/Integrations.tsx"], cwd=ROOT)
    print(f"   ✓ Restored file to commit: {target_commit}")
else:
    print("   [WARN] Could not find the exact commit. Using current file.")

# ═════════════════════════════════════════════════════════════════════
# 2. Safely inject SMS and WhatsApp fields
# ═════════════════════════════════════════════════════════════════════
print("\n==> Injecting SMS and WhatsApp settings into the restored file...")
txt = fe_path.read_text(encoding="utf-8")

# 2a. Inject into useState
form_match = re.search(r"useState\(\{([\s\S]*?)\}\)", txt)
if form_match:
    state_content = form_match.group(1)
    new_fields = '''
    sms_api_key: "",
    sms_sender_id: "",
    whatsapp_phone_id: "",
    whatsapp_token: "",
    '''
    if "sms_api_key" not in state_content:
        txt = txt.replace(form_match.group(0), f"useState({{{state_content}{new_fields}}})")
        print("   ✓ Added SMS/WhatsApp to form state.")

# 2b. Inject UI into the return statement
return_match = re.search(r"return \(([\s\S]*?)\);", txt)
if return_match:
    return_content = return_match.group(1)
    new_ui = """
      {/* ── SMS & WHATSAPP SETTINGS (Appended) ──────────────────────── */}
      <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="bg-sky-100 p-2 rounded-lg">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-sky-600"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-800">SMS & WhatsApp Integration</h2>
            <p className="text-xs text-slate-500">Configure patient communication channels</p>
          </div>
        </div>
        
        <div className="grid md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <h3 className="font-medium text-slate-700 text-sm border-b pb-2">SMS (Africa's Talking)</h3>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
              <input type="password" name="sms_api_key" value={form.sms_api_key || ""} onChange={handleChange}
                     placeholder="atsk_..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Sender ID / Shortcode</label>
              <input type="text" name="sms_sender_id" value={form.sms_sender_id || ""} onChange={handleChange}
                     placeholder="e.g., NIMBUS"
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none transition" />
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="font-medium text-slate-700 text-sm border-b pb-2">WhatsApp (Meta Cloud API)</h3>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Phone Number ID</label>
              <input type="text" name="whatsapp_phone_id" value={form.whatsapp_phone_id || ""} onChange={handleChange}
                     placeholder="e.g., 1045..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Permanent Access Token</label>
              <input type="password" name="whatsapp_token" value={form.whatsapp_token || ""} onChange={handleChange}
                     placeholder="EAAL..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none transition" />
            </div>
          </div>
        </div>
      </div>
    """
    
    # Insert before the last closing </div> in the return block
    last_div_idx = return_content.rfind("</div>")
    if last_div_idx != -1:
        new_return = return_content[:last_div_idx] + new_ui + return_content[last_div_idx:]
        txt = txt.replace(return_content, new_return)
        print("   ✓ Injected SMS/WhatsApp UI.")

fe_path.write_text(txt, encoding="utf-8")

# ═════════════════════════════════════════════════════════════════════
# 3. Build & Push
# ═════════════════════════════════════════════════════════════════════
npm = npm_path()
if npm:
    print("\n==> Running Vite build...")
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Build succeeded!")
    else:
        print("   ❌ Build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print("     " + line)

print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "fix(ui): restore original integrations UI and append SMS/WhatsApp settings"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. Deploy the frontend on Render.")
print("  2. Your original Mobile Money and Stripe settings are back, with their Test Connection buttons.")
print("  3. Scroll to the bottom of the Integrations page to find the new SMS and WhatsApp configuration.")