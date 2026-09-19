"""
GRLPS application launcher: start/stop GRLPS app process (C2, C3, or any app in config).
Uses selectedApp (or app_key), app_path, known_port, and common settings from config.
Path is normalized (strips surrounding quotes). Reference: GRLPS_PY_API_C3_ALL WebAppController / AppManager.
"""

import os
import socket
import subprocess
import time
from typing import IO, Any, Optional
import logging

from grlps_core.constants import (
    DEFAULT_CONNECTION_TIMEOUT_SECONDS,
    DEFAULT_INITIAL_WAIT_SECONDS,
    DEFAULT_MAX_CONNECTION_ATTEMPTS,
)
from utils.run_context import stamped_filename

# The launched app writes its console output to a file rather than to a pipe:
# a pipe nobody drains fills up and stalls the app once it has logged enough.
DEFAULT_APP_OUTPUT_LOG_NAME = "app_console.log"
DEFAULT_LOG_DIRECTORY = "user_interaction/logs"

# On a failed launch this much of that file is echoed into the session log, so the
# real reason (a .NET stack trace, a port conflict) is visible without opening it.
APP_OUTPUT_TAIL_LINES = 40
APP_OUTPUT_TAIL_MAX_BYTES = 64 * 1024


def _resolve_project_root_from_file(file_path: str) -> str:
    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


def normalize_app_path(app_path: str) -> str:
    """
    Strip surrounding double quotes and whitespace so path works with subprocess.
    Config may store path as '"C:\\Program Files (x86)\\...\\app.exe"' for clarity.
    """
    if not app_path or not isinstance(app_path, str):
        return ""
    s = app_path.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1].strip()
    return s


def resolve_app_output_log_path(common: Any) -> str:
    """
    Path the launched app's console output is written to.

    It sits beside the session log and carries the same run stamp, so the files
    belonging to one run group together. Optional keys in grlps_app_config.json
    common:

    - sessionLogDirectory: folder, shared with the session log
    - appOutputLogFileName: file name only
    - sessionLogPerRun: when true (default) the run stamp is inserted
    """
    if not isinstance(common, dict):
        common = {}

    directory = common.get("sessionLogDirectory")
    if not isinstance(directory, str) or not directory.strip():
        directory = DEFAULT_LOG_DIRECTORY
    directory = directory.strip()
    if not os.path.isabs(directory):
        directory = os.path.join(_resolve_project_root_from_file(__file__), directory)

    name = common.get("appOutputLogFileName")
    if not isinstance(name, str) or not name.strip():
        name = DEFAULT_APP_OUTPUT_LOG_NAME
    name = os.path.basename(name.strip())
    if bool(common.get("sessionLogPerRun", True)):
        name = stamped_filename(name)

    return os.path.normpath(os.path.join(directory, name))


class GrlAppLauncher:
    """
    Launch one GRLPS application (e.g. C2-EPR), wait for it to listen on known_port, then return base URL.
    """

    def __init__(
        self,
        app_path: str,
        known_port: int,
        initial_wait: int = DEFAULT_INITIAL_WAIT_SECONDS,
        connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT_SECONDS,
        max_connection_attempts: int = DEFAULT_MAX_CONNECTION_ATTEMPTS,
        logger: Optional[logging.Logger] = None,
        app_output_log_path: Optional[str] = None,
    ):
        self._raw_path = app_path
        self.app_path = normalize_app_path(app_path)
        self.known_port = known_port
        self.initial_wait = initial_wait
        self.connection_timeout = connection_timeout
        self.max_connection_attempts = max_connection_attempts
        self.logger = logger or logging.getLogger("GrlAppLauncher")
        self.app_output_log_path = app_output_log_path
        self._process: Optional[subprocess.Popen] = None
        self._app_output_handle: Optional[IO[bytes]] = None

    @classmethod
    def from_config(
        cls,
        config_manager,
        app_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> "GrlAppLauncher":
        """Build launcher from UnifiedConfigManager (or any with get_app, get_common)."""
        app = config_manager.get_app(app_key) if hasattr(config_manager, "get_app") else {}
        common = config_manager.get_common() if hasattr(config_manager, "get_common") else {}
        app_path = app.get("app_path", "")
        known_port = app.get("known_port", 5001)
        initial_wait = common.get("initialWait", DEFAULT_INITIAL_WAIT_SECONDS)
        connection_timeout = common.get("connectionTimeout", DEFAULT_CONNECTION_TIMEOUT_SECONDS)
        max_attempts = common.get("maxConnectionAttempts", DEFAULT_MAX_CONNECTION_ATTEMPTS)
        return cls(
            app_path=app_path,
            known_port=known_port,
            initial_wait=initial_wait,
            connection_timeout=connection_timeout,
            max_connection_attempts=max_attempts,
            logger=logger,
            app_output_log_path=resolve_app_output_log_path(common),
        )

    def _is_port_in_use(self, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False

    def _validate_path(self) -> bool:
        if not self.app_path:
            self.logger.error("App path is empty")
            return False
        if not os.path.isfile(self.app_path):
            self.logger.error("App path is not a file: %s", self.app_path)
            return False
        self.logger.debug("App path validated: %s", self.app_path)
        return True

    def _open_app_output(self) -> Any:
        """
        Open the app console log and return it for use as the child's stdout/stderr.
        Falls back to DEVNULL when the file cannot be opened: discarding the output
        is still better than a pipe nobody drains, which stalls the app once full.
        """
        path = self.app_output_log_path
        if not path:
            return subprocess.DEVNULL
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            self._app_output_handle = open(path, "ab")
            self.logger.info("App console output: %s", path)
            return self._app_output_handle
        except Exception as e:
            self.logger.warning("Could not open app console log %s: %s", path, e)
            self._app_output_handle = None
            return subprocess.DEVNULL

    def _close_app_output(self) -> None:
        if not self._app_output_handle:
            return
        try:
            self._app_output_handle.close()
        except Exception:
            pass
        finally:
            self._app_output_handle = None

    def _log_app_output_tail(self, reason: str) -> None:
        """
        Echo the end of the app console log into the session log. Without this a
        startup crash surfaces only as a dead process with no stated cause.
        """
        path = self.app_output_log_path
        if not path or not os.path.isfile(path):
            self.logger.error("%s; no app console output was captured", reason)
            return
        try:
            with open(path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - APP_OUTPUT_TAIL_MAX_BYTES))
                text = fh.read().decode("utf-8", "replace")
        except Exception as e:
            self.logger.error("%s; could not read app console log %s: %s", reason, path, e)
            return

        lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            self.logger.error("%s; app wrote nothing to %s", reason, path)
            return

        tail = lines[-APP_OUTPUT_TAIL_LINES:]
        self.logger.error("%s; last %s line(s) of app output from %s:", reason, len(tail), path)
        for line in tail:
            self.logger.error("  [app] %s", line)

    def _launch_process(self) -> bool:
        if not self._validate_path():
            return False
        try:
            cwd = os.path.dirname(self.app_path)
            self.logger.info("Launching: %s", os.path.basename(self.app_path))
            sink = self._open_app_output()
            self._process = subprocess.Popen(
                [self.app_path],
                stdout=sink,
                stderr=subprocess.STDOUT,
                cwd=cwd,
            )
            time.sleep(1)
            if self._process.poll() is not None:
                self._log_app_output_tail(
                    "Process exited immediately (code={0})".format(self._process.returncode)
                )
                return False
            self.logger.info("Process started (PID=%s)", self._process.pid)
            return True
        except FileNotFoundError:
            self.logger.error("Executable not found: %s", self.app_path)
            return False
        except Exception as e:
            self.logger.error("Launch failed: %s", e)
            return False

    def _wait_for_port(self) -> bool:
        self.logger.info("Waiting %ss for app to initialize...", self.initial_wait)
        time.sleep(self.initial_wait)
        deadline = time.time() + self.connection_timeout
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            if not self._process or self._process.poll() is not None:
                code = self._process.returncode if self._process else None
                self._log_app_output_tail(
                    "Process died while waiting for port (code={0})".format(code)
                )
                return False
            if self._is_port_in_use(self.known_port):
                self.logger.info("App listening on port %s", self.known_port)
                return True
            if attempt >= self.max_connection_attempts:
                break
            time.sleep(2)
        self._log_app_output_tail(
            "Port {0} not ready after {1}s".format(self.known_port, self.connection_timeout)
        )
        return False

    def launch(self) -> Optional[str]:
        """
        Launch the app and wait for it to listen on known_port.
        Returns base URL (e.g. http://localhost:5001) or None on failure.
        """
        if self._is_port_in_use(self.known_port):
            self.logger.info("App already running on port %s", self.known_port)
            return "http://127.0.0.1:{0}".format(self.known_port)

        if not self._launch_process():
            self._close_app_output()
            return None
        if not self._wait_for_port():
            self.stop()
            return None
        return "http://127.0.0.1:{0}".format(self.known_port)

    def stop(self) -> bool:
        """Terminate the app process; force kill if needed."""
        if not self._process:
            self._close_app_output()
            return True
        if self._process.poll() is not None:
            self._close_app_output()
            return True
        try:
            self.logger.info("Stopping process (PID=%s)", self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            return True
        except Exception as e:
            self.logger.error("Error stopping process: %s", e)
            return False
        finally:
            self._process = None
            self._close_app_output()

    def is_running(self) -> bool:
        if self._process and self._process.poll() is None:
            return True
        return self._is_port_in_use(self.known_port)

    def did_start_process(self) -> bool:
        """True if this launcher started the app process (vs reusing an existing one on the port)."""
        return self._process is not None and self._process.poll() is None

    def get_process_pid(self) -> Optional[int]:
        """
        PID for the process started by this launcher, if available.
        Returns None when app was reused (already running) or process is not alive.
        """
        if self._process and self._process.poll() is None:
            return int(self._process.pid)
        return None
