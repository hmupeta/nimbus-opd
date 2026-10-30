from django.urls import include, path
from .report_views import (
    DashboardSummaryView, RevenueByCategoryView,
    InsuranceMixView, ARAgingView
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .tokens import TenantTokenObtainPairView
from .appointment_views import AppointmentViewSet
from .momo_views import MobileMoneyConfigViewSet
from .accounting_views import JournalEntryViewSet
from .finance_views import ChartOfAccountViewSet, SupplierViewSet, BillViewSet, ExpenseViewSet, FixedAssetViewSet
from .gateway_views import PaymentGatewayConfigViewSet
from .billing_views import (
    InsuranceClaimViewSet, InsuranceProviderViewSet,
    InvoiceItemViewSet, InvoiceViewSet, PatientInsuranceViewSet,
    PaymentViewSet,
)
from .platform_views import PlatformStatsView, PlatformTenantViewSet
from .analytics_views import AnalyticsTrendView, AuditLogViewSet, ZReportView
from .views import (
    RadiologyExamViewSet,
    TenantRegistrationView,
    ClinicalNoteViewSet, LabOrderViewSet, LabResultViewSet, LabTestViewSet,
    MedicineViewSet, OrderItemViewSet, OrderViewSet, PatientViewSet,
    PharmacyItemViewSet, PharmacyOrderViewSet, RadiologyOrderViewSet,
    StockMovementViewSet, StockViewSet, TenantViewSet, UserViewSet,
    VisitViewSet, VitalsViewSet, VitalDefinitionViewSet, VitalValueViewSet,
)

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("platform/clinics", PlatformTenantViewSet, basename="platform-clinic")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")
router.register("users", UserViewSet, basename="user")
router.register("patients", PatientViewSet, basename="patient")
router.register("visits", VisitViewSet, basename="visit")
router.register("appointments", AppointmentViewSet, basename="appointment")
router.register("vitals", VitalsViewSet, basename="vitals")
router.register("vital-definitions", VitalDefinitionViewSet, basename="vital-def")
router.register("vital-values", VitalValueViewSet, basename="vital-value")
router.register("notes", ClinicalNoteViewSet, basename="note")
router.register("orders", OrderViewSet, basename="order")
router.register("order-items", OrderItemViewSet, basename="order-item")
router.register("lab-tests", LabTestViewSet, basename="lab-test")
router.register("lab-orders", LabOrderViewSet, basename="lab-order")
router.register("lab-results", LabResultViewSet, basename="lab-result")
router.register("radiology-orders", RadiologyOrderViewSet, basename="rad-order")
router.register("radiology-exams", RadiologyExamViewSet, basename="rad-exam")
router.register("medicines", MedicineViewSet, basename="medicine")
router.register("pharmacy-orders", PharmacyOrderViewSet, basename="pharm-order")
router.register("pharmacy-items", PharmacyItemViewSet, basename="pharm-item")
router.register("stock", StockViewSet, basename="stock")
router.register("stock-movements", StockMovementViewSet, basename="stock-mv")
router.register("insurance-providers", InsuranceProviderViewSet, basename="insurer")
router.register("patient-insurances", PatientInsuranceViewSet, basename="patient-ins")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("invoice-items", InvoiceItemViewSet, basename="invoice-item")
router.register("payments", PaymentViewSet, basename="payment")
router.register("insurance-claims", InsuranceClaimViewSet, basename="claim")
router.register("mobile-money-configs", MobileMoneyConfigViewSet, basename="momo")
router.register("journal-entries", JournalEntryViewSet, basename="journal-entry")
router.register("chart-of-accounts", ChartOfAccountViewSet, basename="coa")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("bills", BillViewSet, basename="bill")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("fixed-assets", FixedAssetViewSet, basename="fixed-asset")
router.register("payment-gateway-configs", PaymentGatewayConfigViewSet, basename="gateway")

urlpatterns = [
    path('analytics/trend/', AnalyticsTrendView.as_view(), name='analytics-trend'),
    path('analytics/z-report/', ZReportView.as_view(), name='z-report'),

    path('platform/stats/', PlatformStatsView.as_view(), name='platform-stats'),
    path('auth/register/', TenantRegistrationView.as_view(), name='register'),
    path('reports/dashboard/', DashboardSummaryView.as_view(), name='report-dashboard'),
    path('reports/revenue-by-category/', RevenueByCategoryView.as_view(), name='report-revenue'),
    path('reports/insurance-mix/', InsuranceMixView.as_view(), name='report-insurance'),
    path('reports/ar-aging/', ARAgingView.as_view(), name='report-ar-aging'),
    path("auth/login/", TenantTokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("", include(router.urls)),
]
