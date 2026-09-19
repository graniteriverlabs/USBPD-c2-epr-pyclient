"""
ConnectionService – application launch, ensure ready, stop, and API handler.
All app lifecycle logic lives here; GRLPSApiClient delegates to this service.
Naming: ensure_app_ready / stop_app (not connect/disconnect) to avoid clash with API "connect" endpoint.
"""
from typing import Optional
import logging
import os

from utils.app_launcher import GrlAppLauncher
from api import GRLPSApiHandler
from grlps_core.constants import DEFAULT_API_TIMEOUT_SECONDS


def _resolve_project_root_from_file(file_path: str) -> str:
    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


def _default_grlps_api_config_path() -> str:
    """Absolute path to config/grlps_api_config.json (repo root), independent of cwd."""
    repo_root = _resolve_project_root_from_file(__file__)
    return os.path.join(repo_root, "config", "grlps_api_config.json")


class ConnectionService:
    """Handles GRLPS application launch, ensure ready, stop, and API handler. Used by GRLPSApiClient."""

    def __init__(
        self,
        config_manager,
        logger: Optional[logging.Logger] = None,
        create_get_test_results_json: bool = False,
    ):
        self._config_manager = config_manager
        self.logger = logger or logging.getLogger("ConnectionService")
        self._launcher: Optional[GrlAppLauncher] = None
        self._base_url: str = ""
        self._api_handler: Optional[GRLPSApiHandler] = None
        self._create_get_test_results_json = bool(create_get_test_results_json)

    def launch_app(self) -> bool:
        """
        Launch the GRLPS application (from config). Blocks until app is ready or fails.
        Returns True if app is running and reachable, False otherwise.
        """
        if not self._launcher:
            self._launcher = GrlAppLauncher.from_config(
                self._config_manager, logger=self.logger
            )
        self._base_url = self._launcher.launch() or ""
        if self._base_url:
            # API base is the local browser app (e.g. http://127.0.0.1:5001). applications.C2-EPR.ip_address
            # is the controller connection address for GET /api/ConnectionSetup/0/<ip> only, not the HTTP host.
            self.logger.info("Application launched at %s", self._base_url)
            api_timeout = DEFAULT_API_TIMEOUT_SECONDS
            try:
                common = self._config_manager.get_common() if hasattr(self._config_manager, "get_common") else {}
                if isinstance(common, dict) and common.get("apiTimeout") is not None:
                    api_timeout = float(common.get("apiTimeout"))
            except Exception:
                api_timeout = DEFAULT_API_TIMEOUT_SECONDS
            self._api_handler = GRLPSApiHandler(
                self._base_url,
                config_path=_default_grlps_api_config_path(),
                logger=self.logger,
                create_get_test_results_json=self._create_get_test_results_json,
                request_timeout=api_timeout,
            )
        return bool(self._base_url)

    def did_launcher_start_app(self) -> bool:
        """True if the app process was started by this script (vs already running on the port)."""
        return bool(self._launcher and self._launcher.did_start_process())

    def get_app_pid(self) -> Optional[int]:
        """
        PID for process started by this launcher, if known.
        Returns None when app was already running and reused.
        """
        if not self._launcher:
            return None
        return self._launcher.get_process_pid()

    def ensure_app_ready(self) -> bool:
        """
        Ensure application is running (launch if not already).
        Returns True if app is ready. Use this instead of 'connect' to avoid clash with API connect.
        """
        if self._base_url and self._launcher and self._launcher.is_running():
            return True
        return self.launch_app()

    def stop_app_details(self) -> dict:
        """
        Stop app with status details for end-user reporting.

        Returns:
          - success: bool
          - alreadyStopped: bool
          - stoppedByLauncher: bool
          - externallyManagedRunning: bool
          - pid: int | None
          - message: str
        """
        self._api_handler = None
        self._base_url = ""

        if not self._launcher:
            return {
                "success": True,
                "alreadyStopped": True,
                "stoppedByLauncher": False,
                "externallyManagedRunning": False,
                "pid": None,
                "message": "Launcher not initialized; app considered already stopped.",
            }

        started_by_launcher = bool(self._launcher.did_start_process())
        pid = self._launcher.get_process_pid()

        if started_by_launcher:
            ok = self._launcher.stop()
            return {
                "success": bool(ok),
                "alreadyStopped": bool(ok),
                "stoppedByLauncher": bool(ok),
                "externallyManagedRunning": False,
                "pid": pid,
                "message": "Stopped launcher-managed process." if ok else "Failed to stop launcher-managed process.",
            }

        # App may be running but not owned by this launcher session.
        running_external = bool(self._launcher.is_running())
        return {
            "success": True,
            "alreadyStopped": not running_external,
            "stoppedByLauncher": False,
            "externallyManagedRunning": running_external,
            "pid": None,
            "message": (
                "App is running but externally managed; not stopped by this client."
                if running_external
                else "App already stopped."
            ),
        }

    def stop_app(self) -> bool:
        """Backward-compatible stop API: return success bool only."""
        return bool(self.stop_app_details().get("success"))

    def get_base_url(self) -> str:
        """Base URL of the running application (e.g. http://127.0.0.1:5001). Empty if not launched."""
        return self._base_url or ""

    def is_app_ready(self) -> bool:
        """True if application is launched and running."""
        return bool(self._base_url) and (self._launcher and self._launcher.is_running())

    def get_api_handler(self) -> Optional[GRLPSApiHandler]:
        """Return API handler when app is launched; None otherwise."""
        return self._api_handler
