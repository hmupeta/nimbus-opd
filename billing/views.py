from django.shortcuts import render

# Create your views here.


# === approval-workflow patch (v2) ===

try:
    from rest_framework.decorators import action as _wf_action
    from rest_framework.response import Response as _wf_Response
    from rest_framework import status as _wf_status
    from rest_framework.exceptions import PermissionDenied as _wf_Deny
    from django.utils import timezone as _wf_tz
    from api.roles import (IsFinanceManager as _IsFM,
                           ACCOUNTANT as _ACCT,
                           FINANCE_MANAGER as _FM,
                           has_role as _has_role)

    def _wf_perform_create(self, serializer):
        u = self.request.user
        if not (u.is_superuser or _has_role(u, _ACCT) or _has_role(u, _FM)):
            raise _wf_Deny("Only Accountant or Finance Manager can create payments.")
        serializer.save(created_by=u, status="pending")

    def _wf_perform_update(self, serializer):
        for k in ("status", "approved_by", "approved_at",
                  "created_by", "rejection_reason"):
            serializer.validated_data.pop(k, None)
        serializer.save()

    def _wf_approve(self, request, pk=None):
        p = self.get_object()
        if p.status == "approved":
            return _wf_Response({"detail": "Already approved."},
                                status=_wf_status.HTTP_400_BAD_REQUEST)
        if p.created_by_id == request.user.id and not request.user.is_superuser:
            return _wf_Response(
                {"detail": "You cannot approve a payment you created."},
                status=_wf_status.HTTP_400_BAD_REQUEST)
        p.status = "approved"
        p.approved_by = request.user
        p.approved_at = _wf_tz.now()
        p.rejection_reason = ""
        p.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason"])
        return _wf_Response({"detail": "Approved.", "status": p.status})

    def _wf_reject(self, request, pk=None):
        p = self.get_object()
        if p.status == "rejected":
            return _wf_Response({"detail": "Already rejected."},
                                status=_wf_status.HTTP_400_BAD_REQUEST)
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return _wf_Response({"detail": "A rejection reason is required."},
                                status=_wf_status.HTTP_400_BAD_REQUEST)
        p.status = "rejected"
        p.approved_by = request.user
        p.approved_at = _wf_tz.now()
        p.rejection_reason = reason
        p.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason"])
        return _wf_Response({"detail": "Rejected.", "status": p.status})

    if "PaymentViewSet" in globals():
        _P = PaymentViewSet
        if not hasattr(_P, "_wf_original_get_queryset"):
            _P._wf_original_get_queryset = _P.get_queryset

        def _wf_get_queryset(self):
            qs = _P._wf_original_get_queryset(self)
            s = self.request.query_params.get("status")
            if s in ("pending", "approved", "rejected"):
                qs = qs.filter(status=s)
            return qs

        _P.perform_create  = _wf_perform_create
        _P.perform_update  = _wf_perform_update
        _P.get_queryset    = _wf_get_queryset
        _P.approve = _wf_action(detail=True, methods=["post"],
                                permission_classes=[_IsFM])(_wf_approve)
        _P.reject  = _wf_action(detail=True, methods=["post"],
                                permission_classes=[_IsFM])(_wf_reject)
    else:
        import logging
        logging.getLogger(__name__).warning(
            "[approval-workflow] PaymentViewSet not found in billing/views.py.")
except Exception as _e:
    import logging
    logging.getLogger(__name__).warning(
        f"[approval-workflow] patch failed: {_e}")
