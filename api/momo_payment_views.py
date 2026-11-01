import uuid
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from billing.models import Invoice, Payment
from billing.momo_models import MomoTransaction
from billing.mtn_service import MTNMoMoService
from tenants.models import MobileMoneyConfig
from api.permissions import require_roles

class MomoRequestToPayView(APIView):
    permission_classes = [require_roles("admin", "receptionist")]
    
    def post(self, request):
        invoice_id = request.data.get("invoice_id")
        phone = request.data.get("phone_number")
        config_id = request.data.get("config_id")
        
        if not all([invoice_id, phone, config_id]):
            return Response({"detail": "Missing fields"}, status=400)
            
        invoice = Invoice.all_objects.filter(id=invoice_id).first()
        # MobileMoneyConfig uses a standard manager (objects), not all_objects
        config = MobileMoneyConfig.objects.filter(id=config_id).first()
        
        if not invoice or not config:
            return Response({"detail": "Invoice or config not found"}, status=404)
            
        ref_id = str(uuid.uuid4())
        amount = invoice.balance
        
        try:
            service = MTNMoMoService(config)
            service.request_to_pay(
                amount=amount,
                phone=phone,
                reference_id=ref_id,
                external_id=invoice.invoice_no,
                payer_message=f"Payment for {invoice.invoice_no}"
            )
            
            txn = MomoTransaction.objects.create(
                tenant=request.user.tenant,
                invoice=invoice,
                reference_id=ref_id,
                phone_number=phone,
                amount=amount,
                status=MomoTransaction.Status.PENDING,
                external_id=invoice.invoice_no
            )
            
            return Response({"detail": "Request sent to phone", "reference_id": ref_id}, status=202)
            
        except Exception as e:
            return Response({"detail": str(e)}, status=400)


class MomoStatusCheckView(APIView):
    permission_classes = [require_roles("admin", "receptionist")]
    
    def get(self, request, reference_id):
        txn = MomoTransaction.all_objects.filter(reference_id=reference_id).first()
        if not txn:
            return Response({"detail": "Transaction not found"}, status=404)
            
        config = MobileMoneyConfig.objects.filter(tenant=txn.tenant, provider="mtn_momo").first()
        if not config:
            return Response({"detail": "MoMo config missing"}, status=404)
            
        try:
            service = MTNMoMoService(config)
            new_status = service.check_status(reference_id)
            
            if new_status == "SUCCESSFUL" and txn.status != "SUCCESSFUL":
                txn.status = MomoTransaction.Status.SUCCESSFUL
                txn.save()
                # Auto-create the payment record in the billing system
                Payment.objects.create(
                    invoice=txn.invoice,
                    amount=txn.amount,
                    method=Payment.Method.MOBILE_MONEY,
                    reference=reference_id,
                    received_by=request.user,
                    notes="MTN MoMo Auto-Payment"
                )
            elif new_status == "FAILED":
                txn.status = MomoTransaction.Status.FAILED
                txn.save()
                
            return Response({"status": new_status})
        except Exception as e:
            return Response({"detail": str(e)}, status=400)


class MomoCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        ref_id = request.data.get("referenceId")
        status_str = request.data.get("status")
        
        if not ref_id:
            return Response({"detail": "No referenceId"}, status=400)
            
        txn = MomoTransaction.all_objects.filter(reference_id=ref_id).first()
        if not txn:
            return Response({"detail": "Txn not found"}, status=404)
            
        txn.status = status_str
        if status_str == "FAILED":
            txn.failure_reason = request.data.get("reason", "")
        txn.save()
        
        if status_str == "SUCCESSFUL":
            Payment.objects.create(
                invoice=txn.invoice,
                amount=txn.amount,
                method=Payment.Method.MOBILE_MONEY,
                reference=ref_id,
                received_by=txn.invoice.patient.created_by if hasattr(txn.invoice.patient, 'created_by') else None,
                notes="MTN MoMo Callback Auto-Payment"
            )
            
        return Response({"status": "ok"}, status=200)