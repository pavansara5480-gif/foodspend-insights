"""Consistent JSON errors: {"error": {"code": ..., "message": ..., "details": ...}}."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler

from foodspend_core.recommender import ScenarioError

from .services import NoDataError


def exception_handler(exc, context):
    if isinstance(exc, ScenarioError):
        return Response({"error": {"code": "invalid_input", "message": str(exc)}}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, NoDataError):
        return Response({"error": {"code": "no_data", "message": str(exc)}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    response = drf_handler(exc, context)
    if response is not None:
        detail = response.data
        message = detail.get("detail") if isinstance(detail, dict) and "detail" in detail else "Invalid request"
        response.data = {"error": {"code": getattr(exc, "default_code", "error"), "message": str(message),
                                   "details": None if message == detail.get("detail", None) else detail}
                         } if isinstance(detail, dict) else {"error": {"code": "error", "message": str(detail)}}
    return response
