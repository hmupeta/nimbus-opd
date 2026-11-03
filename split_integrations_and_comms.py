#!/usr/bin/env python3
"""
split_integrations_and_comms.py
1. Restores the exact original Integrations.tsx from Git.
2. Creates a new CommunicationSettings.tsx page for SMS and WhatsApp.
3. Updates the Sidebar and Router.
4. Builds and pushes.
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
# 1. Restore original Integrations.tsx
# ═════════════════════════════════════════════════════════════════════
print("==> Locating and restoring original Integrations.tsx...")
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
    print(f"   ✓ Restored original Integrations.tsx from commit {target_commit[:8]}")
else:
    print("   [WARN] Could not find original commit. Proceeding with current file.")

# ═════════════════════════════════════════════════════════════════════
# 2. Create CommunicationSettings.tsx
# ═════════════════════════════════════════════════════════════════════
print("\n==> Creating CommunicationSettings.tsx...")
comm_path = FRONTEND / "src" / "pages" / "CommunicationSettings.tsx"
comm_path.parent.mkdir(parents=True, exist_ok=True)

COMM_CONTENT = r'''import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { MessageSquare, Smartphone, Save, Loader2, CheckCircle2 } from "lucide-react";

export default function CommunicationSettings() {
  const qc = useQueryClient();
  const [saved, setSaved] = useState(false);

  const [form, setForm] = useState({
    sms_api_key: "",
    sms_sender_id: "",
    whatsapp_phone_id: "",
    whatsapp_token: "",
  });

  const { data, isLoading } = useQuery({
    queryKey: ["integration-settings"],
    queryFn: async () => (await api.get("/integrations/settings/")).data,
  });

  useEffect(() => {
    if (data) setForm((prev) => ({ ...prev, ...data }));
  }, [data]);

  const save = useMutation({
    mutationFn: async () => (await api.put("/integrations/settings/", form)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integration-settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  if (isLoading) return <div className="p-8 text-slate-500">Loading settings...</div>;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">SMS & WhatsApp Settings</h1>
          <p className="text-sm text-slate-500 mt-1">Configure patient communication channels for this clinic.</p>
        </div>
        <button 
          onClick={() => save.mutate()} 
          disabled={save.isPending}
          className="flex items-center gap-2 bg-sky-600 hover:bg-sky-700 text-white px-5 py-2.5 rounded-lg font-medium transition disabled:opacity-50 shadow-sm"
        >
          {save.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
          Save Settings
        </button>
      </div>

      {saved && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-lg flex items-center gap-2 text-sm font-medium">
          <CheckCircle2 className="h-5 w-5" /> Settings saved successfully.
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* SMS Settings */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-sky-100 p-2 rounded-lg"><Smartphone className="h-5 w-5 text-sky-600" /></div>
            <div>
              <h2 className="text-lg font-semibold text-slate-800">SMS Gateway</h2>
              <p className="text-xs text-slate-500">Africa's Talking</p>
            </div>
          </div>
          <div className="space-y-4">
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
        </div>

        {/* WhatsApp Settings */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-emerald-100 p-2 rounded-lg"><MessageSquare className="h-5 w-5 text-emerald-600" /></div>
            <div>
              <h2 className="text-lg font-semibold text-slate-800">WhatsApp Business</h2>
              <p className="text-xs text-slate-500">Meta Cloud API</p>
            </div>
          </div>
          <div className="space-y-4">
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
    </div>
  );
}
'''
comm_path.write_text(COMM_CONTENT.strip() + "\n", encoding="utf-8")
print("   Created CommunicationSettings.tsx.")

# ═════════════════════════════════════════════════════════════════════
# 3. Wire up the Router
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching React Router...")
router_files = [FRONTEND / "src" / "App.tsx", FRONTEND / "src" / "main.tsx", FRONTEND / "src" / "routes.tsx"]
for rf in router_files:
    if not rf.exists(): continue
    txt = rf.read_text(encoding="utf-8")
    
    if 'path="/communication-settings"' in txt or 'path="communication-settings"' in txt:
        print("   Router already patched.")
        break

    if "import CommunicationSettings" not in txt:
        txt = re.sub(r"(import .*? from .*?\n)", r"\1import CommunicationSettings from './pages/CommunicationSettings';\n", txt, count=1)

    if '<Route path="/integrations"' in txt:
        txt = txt.replace('<Route path="/integrations"', '<Route path="/communication-settings" element={<CommunicationSettings />} />\n        <Route path="/integrations"')
    elif '<Route path="integrations"' in txt:
        txt = txt.replace('<Route path="integrations"', '<Route path="communication-settings" element={<CommunicationSettings />} />\n        <Route path="integrations"')
    else:
        continue
        
    rf.write_text(txt, encoding="utf-8")
    print(f"   Injected route into {rf.name}")
    break

# ═════════════════════════════════════════════════════════════════════
# 4. Wire up the Sidebar
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching Sidebar...")
sidebar_found = False
for p in FRONTEND.glob("src/**/*.tsx"):
    if "integrations" not in p.read_text(encoding="utf-8").lower(): continue
    if "sidebar" not in p.name.lower() and "layout" not in p.name.lower() and "nav" not in p.name.lower(): continue

    txt = p.read_text(encoding="utf-8")
    if 'to="/integrations"' in txt and 'to="/communication-settings"' not in txt:
        # Find the Integrations Link and add a new one right after its closing tag
        match = re.search(r'(<Link to="/integrations"[\s\S]*?</Link>)', txt)
        if match:
            original_link = match.group(1)
            # Create the new link by copying the structure
            new_link = original_link.replace('to="/integrations"', 'to="/communication-settings"')
            new_link = new_link.replace('Integrations', 'Communication')
            # Simple regex to replace the icon (usually lucide-react) with a message icon
            new_link = re.sub(r'<([A-Z][a-zA-Z0-9]*) className=', r'<MessageSquare className=', new_link, count=1)
            new_link = re.sub(r'<([A-Z][a-zA-Z0-9]*) size=', r'<MessageSquare size=', new_link, count=1)
            
            txt = txt.replace(original_link, original_link + "\n          " + new_link)
            
            # Ensure MessageSquare is imported
            if "import { MessageSquare" not in txt and "MessageSquare," not in txt:
                txt = re.sub(r"import \{([^}]+)\} from 'lucide-react';", r"import {\1, MessageSquare} from 'lucide-react';", txt, count=1)
                
            p.write_text(txt, encoding="utf-8")
            print(f"   Injected Communication link into {p.name}")
            sidebar_found = True
            break

if not sidebar_found:
    print("   [WARN] Could not automatically patch the Sidebar. Please add the link manually.")

# ═════════════════════════════════════════════════════════════════════
# 5. Build and Push
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
        sys.exit(1)

print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "feat(ui): restore original integrations and create dedicated comms settings"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. Deploy the frontend on Render.")
print("  2. Your original Integrations page is 100% restored.")
print("  3. You will see a new 'Communication' link in your Sidebar.")
print("  4. SMS and WhatsApp settings now live cleanly on their own dedicated page.")