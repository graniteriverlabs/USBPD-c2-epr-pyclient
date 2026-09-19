"""
Msgbox storage: save message and reply to JSON for debugging.
Python 3.x only. All msgbox code lives in the msgbox folder.
"""

import errno
import json
import os
import threading

from typing import List, Dict, Any, Optional


class MsgBoxStorage(object):
    """Saves msgbox message and reply to a JSON file. Thread-safe append."""

    DEFAULT_FILENAME = "msgbox_log.json"

    def __init__(self, log_dir=None, log_filename=None, logger=None):
        """
        :param log_dir: Directory for the JSON file. If None, uses current dir.
        :param log_filename: JSON file name (e.g. "msgbox_log.json"). If None, uses DEFAULT_FILENAME.
        :param logger: Optional logger for debug/error.
        """
        self.log_dir = log_dir or os.getcwd()
        self.log_filename = log_filename if log_filename else self.DEFAULT_FILENAME
        self.logger = logger
        self._records = []  # in-memory list of {timestamp, message, reply, response_sent}
        self._lock = threading.Lock()
        self._filename = os.path.join(self.log_dir, self.log_filename)

    def save(self, message, reply=None, response_sent=False):
        """
        Append one record: message text, reply sent (e.g. "OK" or button name), and whether response was sent.
        """
        import time
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "message": message if message is not None else "",
            "reply": reply if reply is not None else "",
            "response_sent": bool(response_sent),
        }
        with self._lock:
            self._records.append(record)
        if self.logger:
            self.logger.debug("[msgbox] Saved: %s", record.get("message", "")[:50])
        # Persist immediately so short scripts (e.g. client.start() then exit) still get a file;
        # flush used to run only on monitor stop(), which often never runs before process exit.
        self.flush_to_file()

    def flush_to_file(self):
        """Write in-memory records to JSON file (append to existing list in file). Creates file even when no new records so path exists after run."""
        with self._lock:
            to_write = list(self._records)
            self._records = []
        try:
            # Ensure directory exists (so file can be written and user sees path after run)
            if self.log_dir and not os.path.isdir(self.log_dir):
                try:
                    os.makedirs(self.log_dir)
                except OSError as e:
                    if getattr(e, "errno", None) != errno.EEXIST:
                        if self.logger:
                            self.logger.warning("[msgbox] Could not create log dir %s: %s", self.log_dir, e)
            existing = []
            if os.path.isfile(self._filename):
                try:
                    with open(self._filename, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    if not isinstance(existing, list):
                        existing = []
                except Exception:
                    existing = []
            existing.extend(to_write)
            with open(self._filename, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            if self.logger:
                self.logger.info("[msgbox] Flushed %s records to %s", len(to_write), self._filename)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error("[msgbox] Failed to flush: %s", e)
            return False

    def get_pending_count(self):
        """Number of records not yet flushed."""
        with self._lock:
            return len(self._records)
