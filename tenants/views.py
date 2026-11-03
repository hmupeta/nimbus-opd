from django.shortcuts import render

# Create your views here.


from .models import IntegrationSettings
from .serializers import IntegrationSettingsSerializer

class IntegrationSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({"detail": "No tenant assigned."}, status=400)
        
        obj, _ = IntegrationSettings.objects.get_or_create(tenant=tenant)
        return Response(IntegrationSettingsSerializer(obj).data)

    def put(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({"detail": "No tenant assigned."}, status=400)
        
        obj, _ = IntegrationSettings.objects.get_or_create(tenant=tenant)
        serializer = IntegrationSettingsSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
