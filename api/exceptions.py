from rest_framework.views import exception_handler
from rest_framework.response import Response
import traceback

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    # If response is None, it means Django raised an unhandled 500 error.
    # We catch it, print it to the Render logs, and return it as JSON.
    if response is None:
        print("\n--- UNHANDLED EXCEPTION ---")
        print(traceback.format_exc())
        print("---------------------------\n")
        
        return Response({
            "detail": str(exc),
            "traceback": traceback.format_exc()
        }, status=500)
        
    return response
