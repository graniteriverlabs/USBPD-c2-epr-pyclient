"""
Msgbox monitor: separate thread that polls GetMessageBox, saves message and reply, sends response.
Python 3.x only. Reference: GRLPS_PY_API_C3_ALL popup_monitor.
"""

import threading
import time
import re
import unicodedata

from .msgbox_detector import detect_popup
from .msgbox_responder import build_response_data, send_response
from .msgbox_storage import MsgBoxStorage


class MsgBoxMonitor(object):
    """
    Runs a daemon thread that periodically checks for message box (GetMessageBox),
    saves the message, sends a default response (PutMessageBoxResponse), and saves the reply.
    """

    def __init__(self, logger=None, log_dir=None, log_filename=None, poll_interval_sec=0.5, default_response_button="OK"):
        """
        :param logger: Optional logger for debug/info/error.
        :param log_dir: Directory for the JSON file. If None, uses current working dir.
        :param log_filename: JSON file name (e.g. "msgbox_log.json"). If None, uses MsgBoxStorage.DEFAULT_FILENAME.
        :param poll_interval_sec: Seconds between GetMessageBox checks.
        :param default_response_button: Default button to send (e.g. "OK", "Yes").
        """
        self.logger = logger
        self.storage = MsgBoxStorage(log_dir=log_dir, log_filename=log_filename, logger=logger)
        self.poll_interval_sec = poll_interval_sec
        self.default_response_button = default_response_button
        self._api_handler = None
        self._thread = None
        self._active = False
        self._lock = threading.Lock()
        # Active popup state:
        # - respond once when a non-empty message appears
        # - suppress further responses while the same message remains active
        # - clear only after a couple polls return no message (tolerate flicker)
        self._active_popup_message_norm = None
        self._empty_polls = 0
        self._empty_clear_after_polls = 2

    @staticmethod
    def _normalize_message(message: str) -> str:
        """Normalize popup message for de-dup comparisons."""
        if message is None:
            return ""
        s = str(message)
        # Normalize unicode to reduce differences in visually-equal text.
        s = unicodedata.normalize("NFKC", s)
        # Remove non-printable / control / zero-width characters.
        s = "".join(ch for ch in s if (ch.isprintable() or ch.isspace()))
        # Collapse whitespace.
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _messages_match(active_norm: str, new_norm: str) -> bool:
        """Fuzzy match so visually-equal messages compare as equal."""
        if not active_norm or not new_norm:
            return False
        if active_norm == new_norm:
            return True
        # Allow containment to handle tiny invisible/format differences.
        return active_norm in new_norm or new_norm in active_norm

    def set_api_handler(self, handler):
        """Set the API handler (GRLPSApiHandler) used for GetMessageBox and PutMessageBoxResponse."""
        with self._lock:
            self._api_handler = handler
        if self.logger:
            self.logger.debug("[msgbox] API handler set")

    def start(self):
        """Start the background thread. No-op if already running."""
        with self._lock:
            if self._active:
                if self.logger:
                    self.logger.debug("[msgbox] Monitor already active")
                return
            self._active = True
            self._thread = threading.Thread(target=self._run_loop, name="MsgBoxMonitor")
            self._thread.daemon = True
            self._thread.start()
        if self.logger:
            self.logger.info("[msgbox] Monitor thread started; log file: %s", self.storage._filename)

    def stop(self):
        """Stop the background thread and flush storage to file."""
        with self._lock:
            self._active = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.storage.flush_to_file()
        if self.logger:
            self.logger.info("[msgbox] Monitor thread stopped; log saved to: %s", self.storage._filename)

    def _run_loop(self):
        """Thread entry: poll for popup, save message, respond, save reply."""
        if self.logger:
            self.logger.debug("[msgbox] Loop started")
        while self._active:
            try:
                with self._lock:
                    handler = self._api_handler
                if not handler:
                    time.sleep(self.poll_interval_sec)
                    continue
                popup_data = detect_popup(handler)
                message = ""
                message_norm = ""
                if popup_data:
                    message = popup_data.get("message") or ""
                    message_norm = self._normalize_message(message)

                if message_norm:
                    # We have an active popup message.
                    self._empty_polls = 0
                    if self._active_popup_message_norm is None or not self._messages_match(
                        self._active_popup_message_norm, message_norm
                    ):
                        # New popup instance (or a different message): respond once.
                        self._active_popup_message_norm = message_norm
                        if self.logger:
                            self.logger.info("[msgbox] Detected: %s", message[:80])
                        response_data = build_response_data(popup_data, self.default_response_button)
                        ok = send_response(handler, response_data)
                        self.storage.save(
                            message=message,
                            reply=self.default_response_button,
                            response_sent=ok,
                        )
                        if self.logger:
                            self.logger.info("[msgbox] Response sent: %s", "OK" if ok else "FAIL")
                    else:
                        # Same message still active: suppress repeated PUT.
                        if self.logger:
                            self.logger.debug("[msgbox] Active popup unchanged; skipping response")
                else:
                    # No message in popup payload -> count empties and clear active state after a couple polls.
                    self._empty_polls += 1
                    if self._empty_polls >= self._empty_clear_after_polls:
                        self._active_popup_message_norm = None
                        self._empty_polls = 0
            except Exception as e:
                if self.logger:
                    self.logger.error("[msgbox] Loop error: %s", e)
            time.sleep(self.poll_interval_sec)
        if self.logger:
            self.logger.debug("[msgbox] Loop ended")
