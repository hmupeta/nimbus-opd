from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounting.models import JournalEntry
from api.serializers import JournalEntrySerializer
from api.permissions import require_roles


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = JournalEntrySerializer
    permission_classes = [require_roles("admin", "accountant", "finance_manager")]

    def get_queryset(self):
        return JournalEntry.all_objects.all().order_by("-id")

    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "finance_manager")])
    def approve(self, request, pk=None):
        je = self.get_object()
        if je.status != JournalEntry.Status.PENDING:
            return Response({"detail": "Only pending entries can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        
        je.status = JournalEntry.Status.APPROVED
        je.approved_by = request.user
        je.approved_at = timezone.now()
        je.save()
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "finance_manager")])
    def reject(self, request, pk=None):
        je = self.get_object()
        if je.status != JournalEntry.Status.PENDING:
            return Response({"detail": "Only pending entries can be rejected."}, status=status.HTTP_400_BAD_REQUEST)
        
        je.status = JournalEntry.Status.REJECTED
        je.save()
        return Response({"status": "rejected"})
