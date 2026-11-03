from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

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


class TestMomoView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        # Mock testing the API key with the provider
        api_key = request.data.get("api_key")
        provider = request.data.get("provider")
        if not api_key:
            return Response({"detail": "API Key is required."}, status=400)
        # In a real app, you would make a ping request to Lipila/MoneyUnify here.
        return Response({"detail": f"Successfully connected to {provider} gateway."})
