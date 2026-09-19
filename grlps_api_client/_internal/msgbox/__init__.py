"""
Msgbox: separate thread to poll GetMessageBox, save message and reply, send response.
All code in this folder for easy debugging. Python 3.x only.
Reference: GRLPS_PY_API_C3_ALL popup_framework.
"""

from .msgbox_framework import MsgBoxFramework
from .msgbox_monitor import MsgBoxMonitor
from .msgbox_storage import MsgBoxStorage
from .msgbox_detector import detect_popup
from .msgbox_responder import build_response_data, send_response

__all__ = [
    "MsgBoxFramework",
    "MsgBoxMonitor",
    "MsgBoxStorage",
    "detect_popup",
    "build_response_data",
    "send_response",
]
