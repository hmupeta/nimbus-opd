#!/usr/bin/env python3
"""
add_full_accounting_modules.py
  - Adds Suppliers, Bills (AP), Expenses, Fixed Assets models.
  - Exposes COA, JE, AP, Expenses, Fixed Assets APIs.
  - Creates Frontend UIs for all of them.
  - Updates Sidebar to show these to Accountant/Finance Manager only.
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

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Models ────────────────────────────────────────────────
print("==> Updating accounting/models.py")
write("accounting/models.py", '''\
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from common.models import TenantAwareModel


class ChartOfAccount(TenantAwareModel):
    class AccountType(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        EQUITY = "equity", "Equity"
        REVENUE = "revenue", "Revenue"
        EXPENSE = "expense", "Expense"

    code = models.CharField(max_length=10)
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=AccountType.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "code"], name="uniq_account_code")]
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(TenantAwareModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    date = models.DateField()
    reference = models.CharField(max_length=64, help_text="Invoice #, Bill #, or manual ref")
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey("tenants.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"JE-{self.id} ({self.reference})"

    def verify_balance(self):
        debits = sum(line.debit for line in self.lines.all())
        credits = sum(line.credit for line in self.lines.all())
        if debits != credits:
            raise ValidationError(f"Journal Entry is unbalanced! Debits: {debits}, Credits: {credits}")


class JournalEntryLine(TenantAwareModel):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def save(self, *args, **kwargs):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("A line cannot have both a debit and a credit.")
        super().save(*args, **kwargs)


class Supplier(TenantAwareModel):
    name = models.CharField(max_length=128)
    contact_name = models.CharField(max_length=128, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Bill(TenantAwareModel):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partially Paid"
        PAID = "paid", "Paid"

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="bills")
    reference = models.CharField(max_length=64, blank=True, help_text="Supplier invoice #")
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNPAID)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill {self.id} - {self.supplier.name} (ZMW {self.amount})"


class Expense(TenantAwareModel):
    date = models.DateField()
    category = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT, limit_choices_to={"type": "expense"})
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=32, blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Expense {self.id} - {self.description} (ZMW {self.amount})"


class FixedAsset(TenantAwareModel):
    name = models.CharField(max_length=128)
    category = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT, limit_choices_to={"type": "asset"})
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    useful_life_years = models.PositiveIntegerField(default=5)
    is_disposed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (ZMW {self.purchase_cost})"
''')

# ─── 2. BACKEND: Serializers ───────────────────────────────────────────
print("==> Updating api/serializers.py")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")

# Ensure accounting imports
if "from accounting.models import" in s:
    s = s.replace(
        "from accounting.models import JournalEntry, JournalEntryLine",
        "from accounting.models import ChartOfAccount, JournalEntry, JournalEntryLine, Supplier, Bill, Expense, FixedAsset"
    )

# Append new serializers if missing
if "class ChartOfAccountSerializer" not in s:
    s += '''

class ChartOfAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccount
        fields = ["id", "code", "name", "type", "is_active"]

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "contact_name", "email", "phone", "address", "is_active"]

class BillSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    class Meta:
        model = Bill
        fields = ["id", "supplier", "supplier_name", "reference", "date", "due_date", "amount", "status"]

class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    class Meta:
        model = Expense
        fields = ["id", "date", "category", "category_name", "amount", "description", "payment_method", "is_approved"]

class FixedAssetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    class Meta:
        model = FixedAsset
        fields = ["id", "name", "category", "category_name", "purchase_date", "purchase_cost", "salvage_value", "useful_life_years", "is_disposed"]
'''
sp.write_text(s, encoding="utf-8")

# ─── 3. BACKEND: Views ─────────────────────────────────────────────────
print("==> Creating api/finance_views.py")
write("api/finance_views.py", '''\
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from accounting.models import ChartOfAccount, Supplier, Bill, Expense, FixedAsset
from api.serializers import ChartOfAccountSerializer, SupplierSerializer, BillSerializer, ExpenseSerializer, FixedAssetSerializer
from api.permissions import require_roles
from api.views import TenantScopedViewSet

FINANCE_ROLES = ["admin", "accountant", "finance_manager"]

class ChartOfAccountViewSet(TenantScopedViewSet):
    serializer_class = ChartOfAccountSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return ChartOfAccount.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("code")

class SupplierViewSet(TenantScopedViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return Supplier.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("name")

class BillViewSet(TenantScopedViewSet):
    serializer_class = BillSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return Bill.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("-date")

class ExpenseViewSet(TenantScopedViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return Expense.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("-date")
    
    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "finance_manager")])
    def approve(self, request, pk=None):
        exp = self.get_object()
        exp.is_approved = True
        exp.save()
        return Response({"status": "approved"})

class FixedAssetViewSet(TenantScopedViewSet):
    serializer_class = FixedAssetSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return FixedAsset.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("-purchase_date")
''')

# Wire URLs
print("==> Patching api/urls.py")
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "finance_views" not in u:
    u = u.replace(
        "from .accounting_views import JournalEntryViewSet",
        "from .accounting_views import JournalEntryViewSet\n"
        "from .finance_views import ChartOfAccountViewSet, SupplierViewSet, BillViewSet, ExpenseViewSet, FixedAssetViewSet"
    )
    u = u.replace(
        'router.register("journal-entries", JournalEntryViewSet, basename="journal-entry")',
        'router.register("journal-entries", JournalEntryViewSet, basename="journal-entry")\n'
        'router.register("chart-of-accounts", ChartOfAccountViewSet, basename="coa")\n'
        'router.register("suppliers", SupplierViewSet, basename="supplier")\n'
        'router.register("bills", BillViewSet, basename="bill")\n'
        'router.register("expenses", ExpenseViewSet, basename="expense")\n'
        'router.register("fixed-assets", FixedAssetViewSet, basename="fixed-asset")'
    )
    up.write_text(u, encoding="utf-8")

# ─── 4. RLS MIGRATION ──────────────────────────────────────────────────
print("==> Adding RLS for finance tables")
write("common/migrations/0009_rls_finance.py", '''\
from django.db import migrations

TENANT_TABLES = [
    "accounting_supplier", "accounting_bill", "accounting_expense", "accounting_fixedasset"
]

def enable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(f'ALTER TABLE "{tbl}" ENABLE ROW LEVEL SECURITY;')
            cur.execute(f'ALTER TABLE "{tbl}" FORCE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";')
            cur.execute(f"""
                CREATE POLICY tenant_isolation ON "{tbl}"
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """)

def disable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(f'ALTER TABLE "{tbl}" DISABLE ROW LEVEL SECURITY;')

class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0002_bill_chartofaccount_expense_fixedasset_supplier"),
        ("common", "0008_rls_rad_exam"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
''')

# ─── 5. Run Migrations ─────────────────────────────────────────────────
print("\n==> Running migrations")
sh(PY, "manage.py", "makemigrations", "accounting")
sh(PY, "manage.py", "migrate")

# ─── 6. FRONTEND: Finance Dashboard Pages ──────────────────────────────
print("\n==> Creating Frontend Pages")

# Helper to generate simple table pages
def generate_page(title, endpoint, columns, form_fields):
    fields_html = "".join([f'''
      <label className="block text-sm"><span className="text-slate-600">{f['label']}</span>
        <input type="{f['type']}" name="{f['name']}" required className="mt-1 w-full border rounded-lg px-3 py-2" />
      </label>''' for f in form_fields if f['type'] != 'select'])
    
    selects_html = ""
    for f in form_fields:
        if f['type'] == 'select':
            selects_html += f'''
      <label className="block text-sm"><span className="text-slate-600">{f['label']}</span>
        <select name="{f['name']}" required className="mt-1 w-full border rounded-lg px-3 py-2">
          <option value="">Select...</option>
          {{options.{f['options_key']}?.map((o: any) => <option key={{o.id}} value={{o.id}}>{{o.{f['option_label']}}}</option>)}}
        </select>
      </label>'''
    
    headers = "".join([f'<th className="text-left px-4 py-3">{c["label"]}</th>' for c in columns])
    rows = "".join([f'<td className="px-4 py-3">{{row.{c["key"]}}}</td>' for c in columns])

    return f'''\
import {{ useState }} from "react";
import {{ useQuery, useMutation, useQueryClient }} from "@tanstack/react-query";
import {{ api }} from "../api/client";
import type {{ Paginated }} from "../api/types";

export default function {title.replace(" ", "")}() {{
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const data = useQuery({{
    queryKey: ["{endpoint}"],
    queryFn: async () => (await api.get<Paginated<any>>("/{endpoint}/")).data.results,
  }});
  
  const options = useQuery({{
    queryKey: ["finance-options"],
    queryFn: async () => {{
      const [coa, suppliers] = await Promise.all([
        api.get<Paginated<any>>("/chart-of-accounts/").then(r => r.data.results),
        api.get<Paginated<any>>("/suppliers/").then(r => r.data.results),
      ]);
      return {{ coa, suppliers }};
    }}
  }});

  const createItem = useMutation({{
    mutationFn: async (payload: any) => await api.post("/{endpoint}/", payload),
    onSuccess: () => {{ qc.invalidateQueries({{ queryKey: ["{endpoint}"] }}); setShowForm(false); }},
  }});

  function onSubmit(e: any) {{
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: any = {{}};
    fd.forEach((v, k) => payload[k] = v);
    createItem.mutate(payload);
  }}

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-800">{title}</h1>
        <button onClick={{() => setShowForm(!showForm)}} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700">+ New {title}</button>
      </div>

      {{showForm && (
        <form onSubmit={{onSubmit}} className="bg-white border rounded-xl p-6 shadow-sm grid grid-cols-2 gap-4">
          {fields_html}
          {selects_html}
          <div className="col-span-2 flex justify-end gap-2 pt-4">
            <button type="button" onClick={{() => setShowForm(false)}} className="px-4 py-2 border rounded-lg">Cancel</button>
            <button type="submit" disabled={{createItem.isPending}} className="px-4 py-2 bg-sky-600 text-white rounded-lg">Save</button>
          </div>
        </form>
      )}}

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr>{headers}</tr></thead>
          <tbody className="divide-y">
            {{data.data?.map((row: any) => (
              <tr key={{row.id}} className="hover:bg-slate-50">{rows}</tr>
            ))}}
          </tbody>
        </table>
      </div>
    </div>
  );
}}
'''

write_frontend("src/pages/ChartOfAccounts.tsx", generate_page(
    title="Chart of Accounts", endpoint="chart-of-accounts",
    columns=[{"label":"Code","key":"code"},{"label":"Name","key":"name"},{"label":"Type","key":"type"}],
    form_fields=[{"label":"Code","name":"code","type":"text"},{"label":"Name","name":"name","type":"text"},
                 {"label":"Type (asset, liability, equity, revenue, expense)","name":"type","type":"text"}]
))

write_frontend("src/pages/Suppliers.tsx", generate_page(
    title="Supplier", endpoint="suppliers",
    columns=[{"label":"Name","key":"name"},{"label":"Contact","key":"contact_name"},{"label":"Phone","key":"phone"}],
    form_fields=[{"label":"Name","name":"name","type":"text"},{"label":"Contact Person","name":"contact_name","type":"text"},{"label":"Phone","name":"phone","type":"text"}]
))

write_frontend("src/pages/Expenses.tsx", generate_page(
    title="Expense", endpoint="expenses",
    columns=[{"label":"Date","key":"date"},{"label":"Description","key":"description"},{"label":"Amount","key":"amount"},{"label":"Category","key":"category_name"}],
    form_fields=[{"label":"Date","name":"date","type":"date"},{"label":"Description","name":"description","type":"text"},
                 {"label":"Amount (ZMW)","name":"amount","type":"number"},
                 {"label":"Category","name":"category","type":"select","options_key":"coa","option_label":"name"}]
))

write_frontend("src/pages/FixedAssets.tsx", generate_page(
    title="Fixed Asset", endpoint="fixed-assets",
    columns=[{"label":"Name","key":"name"},{"label":"Purchase Date","key":"purchase_date"},{"label":"Cost","key":"purchase_cost"}],
    form_fields=[{"label":"Name","name":"name","type":"text"},{"label":"Purchase Date","name":"purchase_date","type":"date"},
                 {"label":"Cost (ZMW)","name":"purchase_cost","type":"number"},
                 {"label":"Category","name":"category","type":"select","options_key":"coa","option_label":"name"}]
))

write_frontend("src/pages/AccountsPayable.tsx", generate_page(
    title="Accounts Payable (Bill)", endpoint="bills",
    columns=[{"label":"Supplier","key":"supplier_name"},{"label":"Date","key":"date"},{"label":"Amount","key":"amount"},{"label":"Status","key":"status"}],
    form_fields=[{"label":"Reference","name":"reference","type":"text"},{"label":"Date","name":"date","type":"date"},
                 {"label":"Amount (ZMW)","name":"amount","type":"number"},
                 {"label":"Supplier","name":"supplier","type":"select","options_key":"suppliers","option_label":"name"}]
))

# ─── 7. FRONTEND: Update Sidebar ───────────────────────────────────────
print("==> Updating Layout.tsx")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")

old_finance = '''              {(user?.role === "accountant" || user?.role === "finance_manager" || user?.role === "admin") && (
                <>
                  <NavLink to="/accounting" className={linkClass}>Accounting</NavLink>
                  <NavLink to="/integrations" className={linkClass}>Integrations</NavLink>
                </>
              )}'''

new_finance = '''              {(user?.role === "accountant" || user?.role === "finance_manager" || user?.role === "admin") && (
                <>
                  <NavLink to="/accounting" className={linkClass}>General Ledger</NavLink>
                  <NavLink to="/chart-of-accounts" className={linkClass}>Chart of Accounts</NavLink>
                  <NavLink to="/expenses" className={linkClass}>Expenses</NavLink>
                  <NavLink to="/accounts-payable" className={linkClass}>Accounts Payable</NavLink>
                  <NavLink to="/fixed-assets" className={linkClass}>Fixed Assets</NavLink>
                  <NavLink to="/suppliers" className={linkClass}>Suppliers</NavLink>
                  <NavLink to="/integrations" className={linkClass}>Integrations</NavLink>
                </>
              )}'''

if old_finance in l:
    l = l.replace(old_finance, new_finance)
    lp.write_text(l, encoding="utf-8")
    print("   updated sidebar finance links")

# ─── 8. FRONTEND: Update Router ────────────────────────────────────────
print("==> Updating App.tsx")
ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")

imports = '''
import ChartOfAccounts from "./pages/ChartOfAccounts";
import Suppliers from "./pages/Suppliers";
import Expenses from "./pages/Expenses";
import FixedAssets from "./pages/FixedAssets";
import AccountsPayable from "./pages/AccountsPayable";
'''
routes = '''
          <Route path="/chart-of-accounts" element={<ChartOfAccounts />} />
          <Route path="/suppliers" element={<Suppliers />} />
          <Route path="/expenses" element={<Expenses />} />
          <Route path="/fixed-assets" element={<FixedAssets />} />
          <Route path="/accounts-payable" element={<AccountsPayable />} />
'''

if "ChartOfAccounts" not in a:
    a = a.replace('import AccountingDashboard from "./pages/AccountingDashboard";',
                  'import AccountingDashboard from "./pages/AccountingDashboard";' + imports)
    a = a.replace('<Route path="/accounting" element={<AccountingDashboard />} />',
                  '<Route path="/accounting" element={<AccountingDashboard />} />' + routes)
    ap.write_text(a, encoding="utf-8")
    print("   wired finance routes into App.tsx")

# ─── 9. Build & Push ───────────────────────────────────────────────────
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
r = sh("git", "commit", "-m", "feat(finance): add COA, AP, Expenses, Fixed Assets and update sidebar", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")