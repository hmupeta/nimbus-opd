#!/usr/bin/env python3
"""
add_lab_attachments.py
  - Adds an 'attachment' FileField to LabResult.
  - Updates the Lab API to accept multipart form data.
  - Updates the Lab Dashboard modal to upload files.
  - Updates the Doctor's Visit Timeline to view the attachment.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

FRONTEND = ROOT / "frontend"
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

# ─── 1. BACKEND: Model & Migration ─────────────────────────────────────
print("==> Updating lab/models.py")
mp = ROOT / "lab" / "models.py"
m = mp.read_text(encoding="utf-8")
if "attachment = models.FileField" not in m:
    m = m.replace(
        '    resulted_at = models.DateTimeField(auto_now_add=True)',
        '    attachment = models.FileField(upload_to="lab_results/", null=True, blank=True)\n    resulted_at = models.DateTimeField(auto_now_add=True)'
    )
    mp.write_text(m, encoding="utf-8")
    print("   added attachment field")

print("==> Updating api/serializers.py")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")
if '"attachment"' not in s.split("class LabResultSerializer")[1].split("class ")[0]:
    s = s.replace(
        '        fields = ["id", "lab_order", "value_text", "unit", "flag",\n'
        '                  "comment", "resulted_by", "resulted_at", "verified_by"]',
        '        fields = ["id", "lab_order", "value_text", "unit", "flag",\n'
        '                  "comment", "attachment", "resulted_by", "resulted_at", "verified_by"]'
    )
    sp.write_text(s, encoding="utf-8")
    print("   added attachment to LabResultSerializer")

print("==> Updating api/views.py (LabResult endpoint)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")
old_res = '''        result, created = LabResult.objects.update_or_create(
            lab_order=lo,
            defaults={
                "tenant": lo.tenant,
                "value_text": request.data.get("value_text"),
                "unit": request.data.get("unit", ""),
                "flag": request.data.get("flag", "normal"),
                "comment": request.data.get("comment", ""),
                "resulted_by": request.user,
            }
        )'''

new_res = '''        result, created = LabResult.objects.update_or_create(
            lab_order=lo,
            defaults={
                "tenant": lo.tenant,
                "value_text": request.data.get("value_text"),
                "unit": request.data.get("unit", ""),
                "flag": request.data.get("flag", "normal"),
                "comment": request.data.get("comment", ""),
                "resulted_by": request.user,
            }
        )
        if "attachment" in request.FILES:
            result.attachment = request.FILES["attachment"]
            result.save()
'''
if old_res in v:
    v = v.replace(old_res, new_res)
    vp.write_text(v, encoding="utf-8")
    print("   updated result endpoint to handle file upload")

# ─── 2. BACKEND: Run Migrations ────────────────────────────────────────
print("\n==> Running migrations")
sh(PY, "manage.py", "makemigrations", "lab")
sh(PY, "manage.py", "migrate")

# ─── 3. FRONTEND: Lab Dashboard (Upload Modal) ─────────────────────────
print("\n==> Updating LabDashboard.tsx")
ldp = FRONTEND / "src" / "pages" / "LabDashboard.tsx"
ld = ldp.read_text(encoding="utf-8")

# Update mutation to use FormData
old_mut = '''  const submitResult = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: any }) => {
      await api.post(`/lab-orders/${id}/result/`, payload);
    },'''

new_mut = '''  const submitResult = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: FormData }) => {
      await api.post(`/lab-orders/${id}/result/`, payload, {
        headers: { "Content-Type": "multipart/form-data" }
      });
    },'''
if old_mut in ld:
    ld = ld.replace(old_mut, new_mut)

# Update form submission to use FormData
old_submit = '''    const fd = new FormData(e.currentTarget);
    submitResult.mutate({
      id: activeOrder.id,
      payload: fd, // Pass FormData directly
    });'''
# The previous script already made it pass FormData directly, but we need to add the file input to the HTML.
# Let's check if the file input is there.
if 'name="attachment"' not in ld:
    old_comment_input = '''              <label className="block text-sm">
                <span className="text-slate-600">Comments</span>
                <textarea name="comment" rows={2} className="mt-1 w-full border rounded px-3 py-2" />
              </label>'''
    new_comment_input = '''              <label className="block text-sm">
                <span className="text-slate-600">Comments</span>
                <textarea name="comment" rows={2} className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Attach Result Slip (PDF / Image)</span>
                <input type="file" name="attachment" accept="image/*,application/pdf" className="mt-1 w-full border rounded px-3 py-2 bg-white" />
              </label>'''
    ld = ld.replace(old_comment_input, new_comment_input)
    ldp.write_text(ld, encoding="utf-8")
    print("   added file input to LabDashboard modal")

# ─── 4. FRONTEND: Visit Timeline (View Link) ───────────────────────────
print("==> Updating VisitTimeline.tsx")
vt = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v_content = vt.read_text(encoding="utf-8")

if "l.result.attachment" not in v_content:
    old_lab_display = '''                      {l.result.comment && <p>Comment: {l.result.comment}</p>}
                    </div>
                  )}
                </div>'''
    new_lab_display = '''                      {l.result.comment && <p>Comment: {l.result.comment}</p>}
                      {l.result.attachment && (
                        <a href={l.result.attachment} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sky-600 hover:underline font-medium">
                          View Result Attachment ↗
                        </a>
                      )}
                    </div>
                  )}
                </div>'''
    v_content = v_content.replace(old_lab_display, new_lab_display)
    vt.write_text(v_content, encoding="utf-8")
    print("   added attachment link to VisitTimeline lab orders")

# ─── 5. FRONTEND: Build & Push ─────────────────────────────────────────
print("\n==> Running local Vite build to verify")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Local Vite build succeeded!")
    else:
        print("   ❌ Local Vite build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print(f"     {line}")
        sys.exit(1)

print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "feat(lab): allow attaching PDF/Image result slips to lab results", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")