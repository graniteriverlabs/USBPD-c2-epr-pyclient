"""
Msgbox responder: build response payload and call PutMessageBoxResponse.
Python 3.x only. Reference: GRLPS_PY_API_C3_ALL popup_responder.
"""

import logging
from typing import Any, Dict

_logger = logging.getLogger(__name__)


def build_response_data(popup_data, response_button="OK"):
    """
    Build the JSON body for PutMessageBoxResponse from popup data.
    Matches C2 scripts (RunTests, OptimumPosition, Test3) and GRLPS_PY_API_C3_ALL popup_responder.
    :param popup_data: dict from GetMessageBox (message, index/popID, title, etc.)
    :param response_button: "OK"/"Ok", "Yes", "No", etc. (API expects "Ok" not "OK")
    :return: dict for API body
    """
    # Keep payload aligned with older QA framework behavior that C2 accepts.
    pop_id = popup_data.get("popID")
    if pop_id is None:
        pop_id = popup_data.get("index")
    if pop_id is None:
        pop_id = 23
    title = popup_data.get("title") or "GRLPS Test Solution"
    message = popup_data.get("message") or ""
    # C2/C3 API expects "Ok" (capital O, lowercase k) for responseButton
    btn = "Ok" if (response_button or "").strip().upper() == "OK" else (response_button or "Ok")
    return {
        "userTextBoxInput": "",
        "responseButton": btn,
        "shouldTextBoxBeAdded": False,
        "isValid": True,
        "popID": pop_id,
        "displayPopUp": False,
        "isDisplayPopUpOpen": False,
        "title": title,
        "message": "",
        "button": "OK",
        "image": "",
        "icon": "Asterisk",
        "isFrontEndPopUp": False,
        "callBackMethod": "",
        "comboBoxEntries": "",
        "comboBoxEntriesFE": [],
        "selectedComboBoxValue": "",
        "selectedComboBoxValueFE": "",
        "onlyDropdownAdded": False,
        "enableTimerOKButton": False,
        "enableCustomUserInputs": False,
        "customInputValues": {},
    }


def send_response(handler, response_data):
    """
    Call PUT_MESSAGE_BOX_RESPONSE with response_data.
    :param handler: GRLPSApiHandler
    :param response_data: dict from build_response_data()
    :return: True if success, False otherwise
    """
    if not handler:
        return False
    try:
        from api import ApiName
        result = handler.call_api(ApiName.PUT_MESSAGE_BOX_RESPONSE, data=response_data)
        if result.is_success and result.value:
            resp = result.value.get("response") or {}
            ok = bool(resp.get("success"))
            if not ok:
                _logger.warning(
                    "[msgbox] PutMessageBoxResponse HTTP layer failed: %s",
                    resp,
                )
            return ok
        if not result.is_success:
            _logger.warning(
                "[msgbox] PutMessageBoxResponse call failed: %s",
                getattr(result, "error", None),
            )
        return False
    except Exception as ex:
        _logger.warning("[msgbox] PutMessageBoxResponse exception: %s", ex, exc_info=True)
        return False
