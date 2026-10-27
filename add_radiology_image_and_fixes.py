#!/usr/bin/env python3
"""
add_radiology_image_and_fixes.py -- Handle image uploads, hide buttons on reported, show to doctor.
"""
from __future__ import annotations

import os
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

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")

# ─── 1. BACKEND: Add ImageField to model & configure Media ─────────────
print("==> Updating radiology/models.py")
rp = ROOT / "radiology" / "models.py"
r = rp.read_text(encoding="utf-8")
if "image = models.ImageField" not in r:
    r = r.replace(
        '    report_url = models.URLField(blank=True)',
        '    report_url = models.URLField(blank=True)\n    image = models.ImageField(upload_to="radiology/", null=True, blank=True)'
    )
    rp.write_text(r, encoding="utf-8")

print("==> Updating config/settings.py (Media)")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")
if "MEDIA_URL" not in s:
    s += "\n\nMEDIA_URL = '/media/'\nMEDIA_ROOT = BASE_DIR / 'media'\n"
    sp.write_text(s, encoding="utf-8")

print("==> Updating config/urls.py (Serve Media)")
up = ROOT / "config" / "urls.py"
u = up.read_text(encoding="utf-8")
if "static(settings.MEDIA_URL" not in u:
    u = u.replace(
        "from django.urls import include, path",
        "from django.urls import include, path\nfrom django.conf import settings\nfrom django.conf.urls.static import static"
    )
    u = u.replace(
        "]",
        "] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)"
    )
    up.write_text(u, encoding="utf-8")

# ─── 2. BACKEND: Update Serializer ─────────────────────────────────────
print("==> Updating api/serializers.py (RadiologyOrderSerializer)")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")
s = s.replace(
    '"report_url", "reported_at"]',
    '"report_url", "image", "reported_at"]'
)
sp.write_text(s, encoding="utf-8")

# ─── 3. BACKEND: Update View to handle multipart ───────────────────────
print("==> Updating api/views.py (RadiologyOrderViewSet.report)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")
old_report = '''    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "radiology")])
    def report(self, request, pk=None):
        ro = self.get_object()
        ser = RadiologyOrderSerializer(ro, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(
            radiologist=request.user,
            status=RadiologyOrder.Status.REPORTED,
            reported_at=timezone.now(),
        )
        return Response(ser.data)'''

new_report = '''    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "radiology")])
    def report(self, request, pk=None):
        ro = self.get_object()
        # request.data handles both JSON and multipart/form-data (files)
        ser = RadiologyOrderSerializer(ro, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(
            radiologist=request.user,
            status=RadiologyOrder.Status.REPORTED,
            reported_at=timezone.now(),
        )
        return Response(ser.data)'''

if old_report in v:
    v = v.replace(old_report, new_report)
    vp.write_text(v, encoding="utf-8")

# ─── 4. MIGRATIONS ─────────────────────────────────────────────────────
print("==> Running migrations")
sh(PY, "manage.py", "makemigrations", "radiology")
sh(PY, "manage.py", "migrate")

# ─── 5. FRONTEND: Update RadiologyDashboard ────────────────────────────
print("==> Updating src/pages/RadiologyDashboard.tsx")
rdp = ROOT / "frontend" / "src" / "pages" / "RadiologyDashboard.tsx"
rd = rdp.read_text(encoding="utf-8")

# 5a. Hide button on reported
old_btn = '''                  <button onClick={() => setActiveOrder(o)} className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700">
                    Enter Report
                  </button>'''
new_btn = '''                  {o.status === "pending" ? (
                    <button onClick={() => setActiveOrder(o)} className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700">
                      Enter Report
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400 font-medium">Reported</span>
                  )}'''
rd = rd.replace(old_btn, new_btn)

# 5b. Update mutation to use FormData for file upload
old_mut = '''    const fd = new FormData(e.currentTarget);
    submitReport.mutate({
      id: activeOrder.id,
      payload: {
        findings: String(fd.get("findings") || ""),
        impression: String(fd.get("impression") || ""),
      },
    });'''
new_mut = '''    const fd = new FormData(e.currentTarget);
    submitReport.mutate({
      id: activeOrder.id,
      payload: fd, // Pass FormData directly
    });'''
rd = rd.replace(old_mut, new_mut)

# 5c. Add file input to the form
old_form = '''              <label className="block text-sm">
                <span className="text-slate-600">Impression / Conclusion</span>
                <textarea name="impression" rows={2} required className="mt-1 w-full border rounded px-3 py-2" placeholder="Normal, abnormal, etc." />
              </label>'''
new_form = '''              <label className="block text-sm">
                <span className="text-slate-600">Impression / Conclusion</span>
                <textarea name="impression" rows={2} required className="mt-1 w-full border rounded px-3 py-2" placeholder="Normal, abnormal, etc." />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Attach Digital Image (JPG/PNG)</span>
                <input type="file" name="image" accept="image/*" className="mt-1 w-full border rounded px-3 py-2 bg-white" />
              </label>'''
rd = rd.replace(old_form, new_form)

rdp.write_text(rd, encoding="utf-8")

# ─── 6. FRONTEND: Add Radiology Card to VisitTimeline ──────────────────
print("==> Updating src/pages/VisitTimeline.tsx")
vp = ROOT / "frontend" / "src" / "pages" / "VisitTimeline.tsx"
v = vp.read_text(encoding="utf-8")

if '<Card title="Radiology orders">' not in v:
    rad_card = '''      <Card title="Radiology orders">
        {(t.rad_orders as any[]).length === 0 ? (
          <p className="text-sm text-slate-500">No radiology orders.</p>
        ) : (
          <ul className="text-sm space-y-3">
            {(t.rad_orders as any[]).map((o) => (
              <li key={o.id} className="flex justify-between items-start py-2 border-b last:border-0">
                <div className="w-full">
                  <div className="flex justify-between items-center w-full mb-1">
                    <span className="font-medium text-slate-700">{o.modality} - {o.body_part}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${o.status === 'reported' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                      {o.status}
                    </span>
                  </div>
                  {o.status === "reported" && (
                    <div className="mt-2 text-xs text-slate-600 bg-slate-50 p-2 rounded border">
                      <p><b>Findings:</b> {o.findings}</p>
                      <p><b>Impression:</b> {o.impression}</p>
                      {o.image && (
                        <a href={o.image} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sky-600 hover:underline font-medium">
                          View Attached Image ↗
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

'''
    v = v.replace('      <Card title="Pharmacy orders">', rad_card + '      <Card title="Pharmacy orders">')
    vp.write_text(v, encoding="utf-8")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> Done. Restart Django server.")