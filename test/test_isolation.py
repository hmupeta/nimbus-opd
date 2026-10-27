from django.test import TestCase
from rest_framework.test import APIClient
from tenants.models import Tenant, User
from patients.models import Patient

class TenantIsolationTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(code="clinic-a", name="Clinic A")
        self.tenant_b = Tenant.objects.create(code="clinic-b", name="Clinic B")
        
        self.user_a = User.objects.create_user(email="admin@a.com", password="pw", tenant=self.tenant_a, role="admin")
        self.user_b = User.objects.create_user(email="admin@b.com", password="pw", tenant=self.tenant_b, role="admin")
        
        self.patient_b = Patient.objects.create(tenant=self.tenant_b, first_name="John", last_name="B")

    def test_rls_blocks_cross_tenant_read(self):
        client = APIClient()
        client.force_authenticate(user=self.user_a) # Logged in as Clinic A
        
        # Clinic A tries to list patients. It should see 0 (because Patient B is in Clinic B)
        response = client.get('/api/patients/')
        self.assertEqual(response.data['count'], 0)

        # Login as Clinic B and try again
        client.force_authenticate(user=self.user_b)
        response = client.get('/api/patients/')
        self.assertEqual(response.data['count'], 1)