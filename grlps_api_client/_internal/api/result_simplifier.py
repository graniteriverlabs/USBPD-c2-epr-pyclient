"""
Result simplifier – convert full API result (internal/detailed) to customer-facing simplified format.
Does not change existing handler or client; callers pass full result into this class/method
to get simplified output. Internal use keeps full details; customer gets simplified data.
"""
from typing import Any, Dict, Optional

from .result import ApiResult


def _content_type_to_return_type(content_type: str) -> str:
    """Map handler content_type to simplified return_type."""
    if content_type == "json":
        return "json"
    return "str"


class ResultSimplifier:
    """
    Converts full API return data into a simplified format for customers.
    Pass the full result (or result.value) into simplify() / simplify_result().
    """

    @staticmethod
    def simplify_response(full_value: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert full success payload (result.value from call_api) to simplified format.
        Use when you have the full detailed dict and want customer-facing shape only.

        :param full_value: The dict from result.value (success case) with keys
                          api_name, request, response.
        :return: Simplified dict: type, return_type, return_data.
        """
        if not full_value or "request" not in full_value or "response" not in full_value:
            return {
                "type": None,
                "return_type": "str",
                "return_data": None,
            }
        request = full_value.get("request") or {}
        response = full_value.get("response") or {}
        method = request.get("method") or ""
        content_type = response.get("content_type") or "text"
        data = response.get("data")
        return {
            "type": method,
            "return_type": _content_type_to_return_type(content_type),
            "return_data": data,
        }

    @staticmethod
    def simplify_result(api_result: ApiResult) -> Dict[str, Any]:
        """
        Convert full ApiResult (from client.call_api) to simplified format.
        Use for customer: pass the whole result; get back simplified dict for both success and failure.

        :param api_result: The ApiResult returned by client.call_api(...).
        :return: Simplified dict. On success: type, return_type, return_data.
                 On failure: type None, return_type "error", return_data None, error (message string).
        """
        if api_result.is_success and api_result.value is not None:
            out = ResultSimplifier.simplify_response(api_result.value)
            return out
        return {
            "type": None,
            "return_type": "error",
            "return_data": None,
            "error": api_result.error or "Unknown error",
        }


# Convenience: module-level function that delegates to the class
def simplify_response(full_value: Dict[str, Any]) -> Dict[str, Any]:
    """Convert full success result.value to simplified format. See ResultSimplifier.simplify_response."""
    return ResultSimplifier.simplify_response(full_value)


def simplify_result(api_result: ApiResult) -> Dict[str, Any]:
    """Convert full ApiResult to simplified format. See ResultSimplifier.simplify_result."""
    return ResultSimplifier.simplify_result(api_result)
