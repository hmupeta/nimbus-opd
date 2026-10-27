#!/usr/bin/env python3
"""
fix_test_setup.py -- Wrap test setup in db_tenant_context so RLS allows inserts.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)

test_code = '''\
from django.test import TestCase
from rest_framework.test import APIClient
from tenants.models import Tenant, User, TenantSettings
from patients.models import Patient
from common.context import db_tenant_context
from django.contrib.auth.hashers import make_password


class TenantIsolationTests(TestCase):
    def setUp(self):
        # 1. Create two isolated tenants
        self.tenant_a = Tenant.objects.create(code="clinic-a", name="Clinic A")
        self.tenant_b = Tenant.objects.create(code="clinic-b", name="Clinic B")
        
        # 2. Create admin users for both (User is not tenant-scoped via RLS)
        self.user_a = User.objects.create(
            email="admin@a.com", password=make_password("pw"), 
            tenant=self.tenant_a, role="admin"
        )
        self.user_b = User.objects.create(
            email="admin@b.com", password=make_password("pw"), 
            tenant=self.tenant_b, role="admin"
        )
        
        # 3. Create tenant settings and patient WITHIN proper tenant context
        #    (RLS requires app.tenant_id to be set)
        with db_tenant_context(self.tenant_a):
            TenantSettings.objects.create(tenant=self.tenant_a)
            
        with db_tenant_context(self.tenant_b):
            TenantSettings.objects.create(tenant=self.tenant_b)
            Patient.objects.create(tenant=self.tenant_b, first_name="John", last_name="B")

    def login(self, email):
        client = APIClient()
        resp = client.post("/api/auth/login/", {"email": email, "password": "pw"})
        token = resp.data.get("access")
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def test_rls_blocks_cross_tenant_read(self):
        # --- Login as Clinic A ---
        client_a = self.login("admin@a.com")
        response = client_a.get("/api/patients/")
        
        # Clinic A should see 0 patients (Patient B is isolated)
        self.assertEqual(response.data["count"], 0, "Clinic A saw Clinic B's data!")

        # --- Login as Clinic B ---
        client_b = self.login("admin@b.com")
        response = client_b.get("/api/patients/")
        
        # Clinic B should see 1 patient
        self.assertEqual(response.data["count"], 1, "Clinic B could not see its own data!")
        
    def test_rls_blocks_cross_tenant_write(self):
        client_a = self.login("admin@a.com")
        
        # Clinic A tries to create a patient and assign it to Clinic B (maliciously)
        payload = {
            "first_name": "Hacker",
            "last_name": "Man",
            "tenant": str(self.tenant_b.id),
        }
        
        response = client_a.post("/api/patients/", payload)
        
        # The backend should force the tenant to be Clinic A
        self.assertEqual(response.status_code, 201)
        
        # Verify it was saved to Clinic A, NOT Clinic B
        with db_tenant_context(self.tenant_a):
            self.assertEqual(Patient.objects.filter(first_name="Hacker").count(), 1)
            
        with db_tenant_context(self.tenant_b):
            self.assertEqual(Patient.objects.filter(first_name="Hacker").count(), 0)
'''

(ROOT / "tests" / "test_isolation.py").write_text(test_code, encoding="utf-8")
print("   rewrote tests/test_isolation.py with proper tenant context")

print("\n==> Running tests...")
try:
    subprocess.run([str(PY), "manage.py", "test", "tests.test_isolation", "-v", "2"], check=True)
except subprocess.CalledProcessError:
    sys.exit(1)