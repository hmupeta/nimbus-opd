#!/usr/bin/env python3
"""
add_staff_and_fix_patients.py
  - Fixes Patient 500 errors with better debugging and robust MRN generation
  - Adds a Staff management page for Clinic Admins to create users
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

FRONTEND = OPD / "frontend"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. Fix Patient 500 Error (api/views.py) ───────────────────────────
print("==> Patching api/views.py (PatientViewSet)")
vp = OPD / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Add perform_create to catch validation errors and return 400 instead of 500
if "def perform_create(self, serializer):\n        try:" not in v:
    old_patient_view = '''class PatientViewSet(TenantScopedViewSet):
    serializer_class = PatientSerializer
    permission_classes = [require_roles(
        "admin", "receptionist", "doctor", "nurse", "pharmacist", "lab", "radiology")]

    def get_queryset(self):'''
    
    new_patient_view = '''class PatientViewSet(TenantScopedViewSet):
    serializer_class = PatientSerializer
    permission_classes = [require_roles(
        "admin", "receptionist", "doctor", "nurse", "pharmacist", "lab", "radiology")]

    def perform_create(self, serializer):
        # Catch database errors (like MRN collision) and return a clear message
        from rest_framework.exceptions import ValidationError
        from django.db import IntegrityError
        try:
            serializer.save()
        except IntegrityError as e:
            raise ValidationError({"detail": f"Database integrity error: {str(e)}"})
        except Exception as e:
            raise ValidationError({"detail": f"Error saving patient: {str(e)}"})

    def get_queryset(self):'''

    v = v.replace(old_patient_view, new_patient_view)
    vp.write_text(v, encoding="utf-8")
    print("   patched PatientViewSet to catch DB errors cleanly")

# ─── 2. Fix MRN Generation Logic (patients/models.py) ──────────────────
print("==> Patching patients/models.py (Robust MRN generation)")
pm = OPD / "patients" / "models.py"
p_content = pm.read_text(encoding="utf-8")

# Replace the next_sequence function to be safer
old_seq = '''def next_sequence(tenant, scope: str) -> int:
    with transaction.atomic():
        seq, _ = TenantSequence.objects.select_for_update().get_or_create(
            tenant=tenant, scope=scope,
        )
        seq.last += 1
        seq.save(update_fields=["last"])
        return seq.last'''

new_seq = '''def next_sequence(tenant, scope: str) -> int:
    with transaction.atomic():
        try:
            # Use select_for_update to prevent race conditions
            seq, _ = TenantSequence.objects.select_for_update().get_or_create(
                tenant=tenant, scope=scope,
            )
            seq.last += 1
            seq.save(update_fields=["last"])
            return seq.last
        except Exception:
            # Fallback for extreme edge cases (e.g. DB lock)
            import time
            time.sleep(0.1)
            seq, _ = TenantSequence.objects.get_or_create(
                tenant=tenant, scope=scope,
            )
            seq.last += 1
            seq.save(update_fields=["last"])
            return seq.last'''

if old_seq in p_content:
    p_content = p_content.replace(old_seq, new_seq)
    pm.write_text(p_content, encoding="utf-8")
    print("   patched next_sequence fallback")

# ─── 3. Create Staff Management UI ─────────────────────────────────────
print("==> Creating src/pages/Staff.tsx")
write_frontend("src/pages/Staff.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

const ROLES = [
  { value: "doctor", label: "Doctor" },
  { value: "nurse", label: "Nurse" },
  { value: "receptionist", label: "Receptionist" },
  { value: "lab", label: "Lab Technician" },
  { value: "radiology", label: "Radiologist" },
  { value: "pharmacist", label: "Pharmacist" },
];

export default function Staff() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const staff = useQuery({
    queryKey: ["staff"],
    queryFn: async () => (await api.get<Paginated<any>>("/users/")).data.results,
  });

  const createStaff = useMutation({
    mutationFn: async (payload: any) => {
      await api.post("/users/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["staff"] });
      setShowForm(false);
    },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createStaff.mutate({
      email: fd.get("email"),
      first_name: fd.get("first_name"),
      last_name: fd.get("last_name"),
      role: fd.get("role"),
      password: fd.get("password"),
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Staff Management</h1>
          <p className="text-sm text-slate-500 mt-1">Create and manage user accounts for your clinic.</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium">
          + Add Staff Member
        </button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="block text-sm">
              <span className="text-slate-600 font-medium">First Name</span>
              <input name="first_name" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-600 font-medium">Last Name</span>
              <input name="last_name" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-600 font-medium">Email Address</span>
              <input type="email" name="email" required className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-600 font-medium">Role</span>
              <select name="role" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="">Select a role...</option>
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </label>
            <label className="block text-sm col-span-2">
              <span className="text-slate-600 font-medium">Temporary Password</span>
              <input type="password" name="password" required minLength={6} className="mt-1 w-full border rounded-lg px-3 py-2" />
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-slate-600 border rounded-lg hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={createStaff.isPending} className="px-4 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-700">
              {createStaff.isPending ? "Creating..." : "Create Account"}
            </button>
          </div>
        </form>
      )}

      {staff.isLoading && <p className="text-slate-500">Loading staff list...</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Email</th>
              <th className="text-left px-4 py-3">Role</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {staff.data?.map((u: any) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{u.first_name} {u.last_name}</td>
                <td className="px-4 py-3 text-slate-500">{u.email}</td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-slate-100 px-2 py-1 rounded capitalize">{u.role}</span>
                </td>
                <td className="px-4 py-3">
                  {u.is_active ? <span className="text-emerald-600 font-medium">Active</span> : <span className="text-red-500 font-medium">Inactive</span>}
                </td>
              </tr>
            ))}
            {staff.data?.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">No staff members found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
''')

# ─── 4. Wire up Navigation and Router ──────────────────────────────────
print("==> Updating Layout and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Staff" not in l:
    l = l.replace(
        '            {isClinicalStaff && user?.role === "admin" && (\n              <>\n                <NavLink to="/reports" className={linkClass}>MIS Reports</NavLink>\n                <NavLink to="/audit" className={linkClass}>Audit Trail</NavLink>\n              </>\n            )}',
        '            {isClinicalStaff && user?.role === "admin" && (\n              <>\n                <NavLink to="/staff" className={linkClass}>Staff</NavLink>\n                <NavLink to="/reports" className={linkClass}>MIS Reports</NavLink>\n                <NavLink to="/audit" className={linkClass}>Audit Trail</NavLink>\n              </>\n            )}'
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")
if "Staff" not in a:
    a = a.replace(
        'import AuditTrail from "./pages/AuditTrail";',
        'import AuditTrail from "./pages/AuditTrail";\nimport Staff from "./pages/Staff";'
    )
    a = a.replace(
        '<Route path="/audit" element={<AuditTrail />} />',
        '<Route path="/audit" element={<AuditTrail />} />\n          <Route path="/staff" element={<Staff />} />'
    )
    ap.write_text(a, encoding="utf-8")
    print("   wired Staff page into router")

# ─── 5. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(patient): robust MRN + error messages. feat(staff): user creation UI",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")
print("\nThen:")
print("  - Go to /patients and try to create a patient. If it fails, you will now see the exact error in a red box.")
print("  - Go to /staff (as Clinic Admin) to create a new Nurse or Doctor.")