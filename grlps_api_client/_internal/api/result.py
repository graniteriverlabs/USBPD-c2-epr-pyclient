"""
Result pattern for API responses (reference: GRLPS_PY_API_C3_ALL API/result.py).
"""
import json
from typing import TypeVar, Generic, Optional, Any, Dict
from enum import Enum

T = TypeVar("T")


class ResultType(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"


class Result(Generic[T]):
    """Result with value, error, and type (success/failure/warning)."""

    def __init__(
        self,
        value: Optional[T] = None,
        error: Optional[str] = None,
        exception: Optional[Exception] = None,
        result_type: Optional[ResultType] = None,
        metadata: Optional[Dict[str, Any]] = None,
        warning_message: Optional[str] = None,
    ):
        self._value = value
        self._error = error
        self._exception = exception
        self._metadata = metadata or {}
        self._warning_message = warning_message
        if result_type is None:
            if error is not None:
                self._result_type = ResultType.FAILURE
            elif warning_message is not None:
                self._result_type = ResultType.WARNING
            else:
                self._result_type = ResultType.SUCCESS
        else:
            self._result_type = result_type

    @property
    def value(self) -> T:
        return self._value

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def warning_message(self) -> Optional[str]:
        return self._warning_message

    @property
    def exception(self) -> Optional[Exception]:
        return self._exception

    @property
    def metadata(self) -> Dict[str, Any]:
        """Optional dict (e.g. result_value on logical failure after HTTP 200)."""
        return dict(self._metadata)

    @property
    def result_type(self) -> ResultType:
        return self._result_type

    @property
    def is_success(self) -> bool:
        return self._result_type == ResultType.SUCCESS

    @property
    def is_failure(self) -> bool:
        return self._result_type == ResultType.FAILURE

    @classmethod
    def success(cls, value: T = None, metadata: Optional[Dict[str, Any]] = None) -> "Result[T]":
        return cls(value=value, result_type=ResultType.SUCCESS, metadata=metadata)

    @classmethod
    def failure(
        cls,
        error: str,
        exception: Optional[Exception] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Result[T]":
        return cls(error=error, exception=exception, result_type=ResultType.FAILURE, metadata=metadata)


ApiResult = Result[Dict[str, Any]]


def _json_safe(value: Any) -> Any:
    """Best-effort conversion so value is JSON-serializable (for json.dumps)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(x) for x in value]
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def api_result_to_json_dict(result: "Result[Any]") -> Dict[str, Any]:
    """
    Convert Result/ApiResult to a plain dict suitable for json.dumps.
    Shape: success, resultType, error, warning, data (payload when success).
    """
    out: Dict[str, Any] = {
        "success": bool(result.is_success),
        "resultType": result.result_type.value,
        "error": result.error,
        "warning": result.warning_message,
        "data": None,
    }
    if result.is_success and result.value is not None:
        out["data"] = _json_safe(result.value)
    elif not result.is_success and result.metadata.get("result_value") is not None:
        out["data"] = _json_safe(result.metadata["result_value"])
    return out
