#!/usr/bin/env python3
"""
fix_timeline_orders_ui.py -- Show detailed order items in the VisitTimeline.
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path.cwd()
FRONTEND = ROOT / "frontend"
vp = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v = vp.read_text(encoding="utf-8")

old_card = '''        {/* ORDERS */}
        <Card title="Orders">
          <ul className="text-sm space-y-1 mb-2">
            {t.orders.map((o) => (
              <li key={o.id} className="flex justify-between items-center py-1 border-b last:border-0">
                <span className="capitalize">{o.kind}</span>
                <span className="text-[10px] font-medium text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{o.status}</span>
              </li>
            ))}
            {t.orders.length === 0 && <li className="text-slate-500">None</li>}
          </ul>'''

new_card = '''        {/* ORDERS */}
        <Card title="Orders">
          <ul className="text-sm space-y-2 mb-2">
            {t.orders.map((o) => (
              <li key={o.id} className="flex flex-col py-1 border-b last:border-0">
                <div className="flex justify-between items-center mb-1">
                  <span className="capitalize font-medium text-slate-700">{o.kind}</span>
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${o.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {o.status}
                  </span>
                </div>
                <ul className="text-xs text-slate-500 pl-2 border-l-2 border-slate-100">
                  {o.items.map(i => (
                    <li key={i.id}>{i.quantity}x {i.description} ({i.code})</li>
                  ))}
                </ul>
              </li>
            ))}
            {t.orders.length === 0 && <li className="text-slate-500">None</li>}
          </ul>'''

if old_card in v:
    v = v.replace(old_card, new_card)
    vp.write_text(v, encoding="utf-8")
    print("   patched VisitTimeline.tsx")