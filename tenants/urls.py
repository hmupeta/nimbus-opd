from .views import IntegrationSettingsView
from django.urls import path

urlpatterns = [
    path('settings/', IntegrationSettingsView.as_view(), name='integration-settings'),]
