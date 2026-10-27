from drf_spectacular.extensions import OpenApiAuthenticationExtension


class TenantJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Tell drf-spectacular that TenantJWTAuthentication uses HTTP bearer + JWT.

    The scheme *name* here ('jwtAuth') must match the securityScheme key used
    in SPECTACULAR_SETTINGS['APPEND_COMPONENTS'] and SPECTACULAR_SETTINGS['SECURITY'].
    """

    target_class = "api.auth.TenantJWTAuthentication"
    name = "jwtAuth"
    match_subclasses = True

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
