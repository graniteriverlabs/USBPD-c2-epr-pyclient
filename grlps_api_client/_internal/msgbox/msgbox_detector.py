"""
Msgbox detector: call GetMessageBox API and return popup data if present.
Python 3.x only.
"""
import logging

_logger = logging.getLogger(__name__)


def detect_popup(handler):
    """
    Call GET_MESSAGE_BOX via handler. Return popup dict (with 'message', 'index'/popID, etc.) or None.
    :param handler: GRLPSApiHandler (or any object with call_api(api_name, **kwargs) returning Result)
    :return: dict or None

    PutMessageBoxResponse is sent only when this returns a dict. The C2 app returns
    ``message: null`` when there is no active popup; we do not send a PUT in that case.
    """
    if not handler:
        return None
    try:
        from api import ApiName
        result = handler.call_api(ApiName.GET_MESSAGE_BOX)
        if not result.is_success or not result.value:
            _logger.debug(
                "[msgbox] GetMessageBox no result: success=%s value=%s err=%s",
                getattr(result, "is_success", None),
                result.value is not None,
                getattr(result, "error", None),
            )
            return None
        response = result.value.get("response") or {}
        if not response.get("success"):
            return None
        data = response.get("data")
        if not isinstance(data, dict):
            _logger.debug("[msgbox] GetMessageBox: unexpected data type %r", type(data).__name__)
            return None
        msg = data.get("message")
        if msg is None or (isinstance(msg, str) and not msg.strip()):
            # No active popup — normal; do not call PutMessageBoxResponse
            return None
        return data
    except Exception as ex:
        _logger.debug("[msgbox] GetMessageBox exception: %s", ex, exc_info=True)
        return None
