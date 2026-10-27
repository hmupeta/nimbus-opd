from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        # Registers the OpenApiAuthenticationExtension for TenantJWTAuthentication
        from . import schema_extensions  # noqa: F401
