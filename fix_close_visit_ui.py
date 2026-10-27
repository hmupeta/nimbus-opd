#!/usr/bin/env python3
"""
fix_close_visit_ui.py -- Show an alert if a visit cannot be closed due to pending orders.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
if not FRONTEND.exists():
    sys.exit(f"Frontend not found at {FRONTEND}.")

vp = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v = vp.read_text(encoding="utf-8")

old_mut = '''  const closeVisit = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/visits/${id}/close/`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] }),
  });'''

new_mut = '''  const closeVisit = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/visits/${id}/close/`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] }),
    onError: (error: any) => {
      // Show a helpful message if the backend rejects closing due to pending orders
      const msg = error.response?.data?.detail || "Failed to close visit. Please check pending orders.";
      alert(`Cannot Close Visit:\\n\\n${msg}`);
    }
  });'''

if old_mut in v:
    v = v.replace(old_mut, new_mut)
    vp.write_text(v, encoding="utf-8")
    print("   patched VisitTimeline.tsx")
else:
    print("   [WARN] Could not find closeVisit mutation block.")

print("==> Done. Refresh your browser.")