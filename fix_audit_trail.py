#!/usr/bin/env python3
"""
fix_audit_trail.py
  - Fixes JWT auth to set the current user in the thread-local context.
  - Upgrades AuditLogSerializer to show human-readable record names and detailed changes.
  - Rewrites the AuditTrail.tsx UI to display the rich data.
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

FRONTEND = ROOT / "frontend"
AP = ROOT / "api" / "auth.py"
SP = ROOT / "api" / "serializers.py"
AT = FRONTEND / "src" / "pages" / "AuditTrail.tsx"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT,
                          capture_output=True, text=True)

# ─── 1. Fix Auth Context (api/auth.py) ─────────────────────────────────
print("==> Patching api/auth.py (Set current user in context)")
a = AP.read_text(encoding="utf-8")
if "set_current_user(user)" not in a:
    a = a.replace(
        "from common.context import set_current_tenant",
        "from common.context import set_current_tenant, set_current_user"
    )
    a = a.replace(
        "            set_current_tenant(user.tenant)",
        "            set_current_tenant(user.tenant)\n            set_current_user(user)"
    )
    # Fallback if the import isn't exactly that
    if "set_current_user" not in a.split("def get_user")[0]:
        a = a.replace(
            "def get_user(self, validated_token):",
            "from common.context import set_current_user\n\n    def get_user(self, validated_token):"
        )
    AP.write_text(a, encoding="utf-8")
    print("   patched auth.py")

# ─── 2. Enhance AuditLogSerializer (api/serializers.py) ────────────────
print("==> Patching api/serializers.py (Rich audit data)")
s = SP.read_text(encoding="utf-8")

new_audit_serializer = '''\
class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="System")
    user_name = serializers.SerializerMethodField()
    record_name = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "at", "user_email", "user_name", "action", "record_name", "changes"]

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.email
        return "System"

    def get_record_name(self, obj):
        if obj.target:
            return str(obj.target)
        return f"{obj.content_type.model.capitalize()} #{obj.object_id}"

    def get_changes(self, obj):
        if not obj.before or not obj.after:
            return {}
        changes = []
        for key, new_val in obj.after.items():
            old_val = obj.before.get(key)
            if old_val != new_val:
                # Don't show raw password hashes or empty dicts
                if key in ["password", "created_at", "updated_at"]: continue
                changes.append({
                    "field": key.replace("_", " ").title(),
                    "old": old_val,
                    "new": new_val
                })
        return changes
'''

# Replace the existing AuditLogSerializer
import re
pattern = re.compile(r"class AuditLogSerializer\(serializers\.ModelSerializer\):.*?(?=\nclass |\Z)", re.DOTALL)
if pattern.search(s):
    s = pattern.sub(new_audit_serializer, s, count=1)
    SP.write_text(s, encoding="utf-8")
    print("   patched serializers.py with rich changes")
else:
    print("   [WARN] Could not find AuditLogSerializer to replace.")

# ─── 3. Rewrite AuditTrail.tsx ─────────────────────────────────────────
print("==> Updating AuditTrail.tsx UI")
CONTENT = '''
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function AuditTrail() {
  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: async () => (await api.get<Paginated<any>>("/audit-logs/")).data.results,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Audit Trail</h1>
        <p className="text-sm text-slate-500 mt-1">A complete log of every data change in the clinic (most recent 200 events).</p>
      </div>

      {isLoading && <p className="text-slate-500">Loading…</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="text-left px-4 py-3 w-32">Time</th>
              <th className="text-left px-4 py-3 w-48">User</th>
              <th className="text-left px-4 py-3 w-24">Action</th>
              <th className="text-left px-4 py-3 w-64">Record</th>
              <th className="text-left px-4 py-3">Changes</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.map((log: any) => (
              <tr key={log.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-500 whitespace-nowrap text-xs">
                  {new Date(log.at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'medium' })}
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-800">{log.user_name}</div>
                  <div className="text-xs text-slate-400">{log.user_email}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wide ${
                    log.action === "create" ? "bg-emerald-100 text-emerald-700" :
                    log.action === "delete" ? "bg-red-100 text-red-700" :
                    "bg-sky-100 text-sky-700"
                  }`}>
                    {log.action}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-medium text-slate-700 block truncate max-w-[240px]" title={log.record_name}>
                    {log.record_name}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs">
                  {log.changes && log.changes.length > 0 ? (
                    <ul className="space-y-1">
                      {log.changes.map((c: any, idx: number) => (
                        <li key={idx} className="bg-slate-50 p-1.5 rounded border border-slate-100">
                          <span className="font-semibold text-slate-600">{c.field}:</span>{" "}
                          <span className="text-red-500 line-through opacity-70">{String(c.old || "empty")}</span>{" "}
                          <span className="text-slate-400">→</span>{" "}
                          <span className="text-emerald-600 font-medium">{String(c.new || "empty")}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-slate-400 italic">No field changes</span>
                  )}
                </td>
              </tr>
            ))}
            {data?.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-slate-500">No audit logs found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
'''
AT.write_text(CONTENT.strip(), encoding="utf-8")
print("   wrote AuditTrail.tsx")

# ─── 4. Build & Push ───────────────────────────────────────────────────
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
r = sh("git", "commit", "-m", "feat(audit): capture user context and display detailed field changes", check=False)
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")