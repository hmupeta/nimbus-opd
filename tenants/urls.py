from .views import IntegrationSettingsView, TestMomoView
from django.urls import path

urlpatterns = [
    path('test-momo/', TestMomoView.as_view(), name='test-momo'),
    path('settings/', IntegrationSettingsView.as_view(), name='integration-settings'),]
