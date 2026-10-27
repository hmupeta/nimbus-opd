#!/usr/bin/env python3
"""
setup_and_run_tests.py -- Create proper test suite using JWT auth for RLS enforcement.
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

# 1. Create the tests folder and files
tests_dir = ROOT / "tests"
tests_dir.mkdir(exist_ok=True)
(tests_dir / "__init__.py").write_text("", encoding="utf-8")

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
        
        TenantSettings.objects.create(tenant=self.tenant_a)
        TenantSettings.objects.create(tenant=self.tenant_b)
        
        # 2. Create admin users for both
        self.user_a = User.objects.create(
            email="admin@a.com", password=make_password("pw"), 
            tenant=self.tenant_a, role="admin"
        )
        self.user_b = User.objects.create(
            email="admin@b.com", password=make_password("pw"), 
            tenant=self.tenant_b, role="admin"
        )
        
        # 3. Create a patient in Clinic B
        with db_tenant_context(self.tenant_b):
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
        
        # Clinic A tries to create a patient and assign it to Clinic B (Maliciously)
        payload = {
            "first_name": "Hacker",
            "last_name": "Man",
            "tenant": str(self.tenant_b.id) # Trying to inject into B
        }
        
        response = client_a.post("/api/patients/", payload)
        
        # The backend should force the tenant to be Clinic A (ignoring the payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["first_name"], "Hacker")
        
        # Verify it was saved to Clinic A, NOT Clinic B
        with db_tenant_context(self.tenant_a):
            self.assertEqual(Patient.objects.filter(first_name="Hacker").count(), 1)
            
        with db_tenant_context(self.tenant_b):
            self.assertEqual(Patient.objects.filter(first_name="Hacker").count(), 0)
'''
(tests_dir / "test_isolation.py").write_text(test_code, encoding="utf-8")
print("   created tests/test_isolation.py")

# 2. Run the tests using the correct dotted notation
print("==> Running tests...")
subprocess.run(
    [str(PY), "manage.py", "test", "tests.test_isolation", "-v", "2"], 
    check=True, env=ENV
)