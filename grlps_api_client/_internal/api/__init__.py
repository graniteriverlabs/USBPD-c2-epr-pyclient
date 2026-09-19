"""
API layer – handler, result, enum (reference: GRLPS_PY_API_C3_ALL).
"""
from .api_enum import ApiName
from .result import Result, ApiResult, api_result_to_json_dict
from .grlps_api_handler import GRLPSApiHandler
from .result_simplifier import ResultSimplifier, simplify_response, simplify_result

__all__ = [
    "ApiName",
    "Result",
    "ApiResult",
    "api_result_to_json_dict",
    "GRLPSApiHandler",
    "ResultSimplifier",
    "simplify_response",
    "simplify_result",
]
