"""
GRLPS API Client — implementation (`GRLPSApiClientCore`).

Runtime logic is split under `grlps_core/` (constants, test-result helpers, mixins)
similar to GRLPS_PY_API_C3_ALL service-style layout. This module defines the
composed class and lifecycle (bootstrap, connection, msgbox, call_api).

`grlps_api_client.GRLPSApiClient` is a thin facade; customers may read
`grlps_api_client.py` and ship this tree as `.pyc` if implementation details
should be hidden.
"""

import time
from typing import Optional, Dict, Any

from utils.bootstrap import initialize_system
from services.connection_service import ConnectionService
from api import ApiName
from api.result import ApiResult, Result, api_result_to_json_dict

from grlps_core.constants import DEFAULT_PROGRESS_FULL_STATES_MAX
from grlps_core.project_vif_mixin import ProjectVifMixin
from grlps_core.test_execution_mixin import TestExecutionMixin
from report_framework import ReportFrameworkService

# Facade / external imports expect this name (see grlps_api_client.py)
_DEFAULT_PROGRESS_FULL_STATES_MAX = DEFAULT_PROGRESS_FULL_STATES_MAX


def _resolve_project_root_from_file(file_path: str) -> str:
    import os

    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


class GRLPSApiClientCore(ProjectVifMixin, TestExecutionMixin):
    """
    Internal implementation of GRLPS API client.
    End-users should call `GRLPSApiClient` facade.
    """

    def __init__(
        self,
        app_config_file: Optional[str] = None,
        logging_config_file: Optional[str] = None,
    ):
        """Initialize client (bootstrap + create connection service)."""
        # Code-only switch: set True when debug GetTestResults JSON files are needed.
        self.create_get_test_results_json = False
        self._config_manager = None
        self._log_manager = None
        self._connection_service: Optional[ConnectionService] = None
        self._app_config_file = app_config_file
        self._logging_config_file = logging_config_file
        self._bootstrap_done = False
        self._msgbox_monitoring_started = False
        self._controller_connected = False
        self._report_framework: Optional[ReportFrameworkService] = None
        self._do_bootstrap()
        self._connection_service = ConnectionService(
            self._config_manager,
            self.logger,
            create_get_test_results_json=self.create_get_test_results_json,
        )
        self._report_framework = ReportFrameworkService(self)

    def _project_root(self) -> str:
        """Project root directory (parent of services)."""
        return _resolve_project_root_from_file(__file__)

    def _do_bootstrap(self) -> None:
        """Internal: one-time bootstrap (config + logging)."""
        if self._bootstrap_done:
            return
        self._config_manager, self._log_manager, self.logger = initialize_system(
            logging_config_file=self._logging_config_file,
            app_config_file=self._app_config_file,
        )
        self._bootstrap_done = True
        self.logger.info("GRLPS API Client initialized")

    @property
    def config_manager(self):
        """Config manager (for advanced use). Prefer get_base_url(), get_selected_app()."""
        return self._config_manager

    def get_selected_app(self) -> str:
        """Selected app name from config (e.g. C2-EPR)."""
        if not self._config_manager:
            return ""
        return self._config_manager.get_selected_app() or ""

    # ---- Delegate to ConnectionService ----
    def launch_app(self) -> bool:
        """
        Launch the GRLPS application (local process / HTTP server up). Returns True if ready.
        This is not the controller "connect" step — use connection_setup() for that.
        Does not start message-box monitoring; for the normal flow use `start()`, which
        includes msgbox monitoring (default) before ConnectionSetup. For granular steps,
        call start_msgbox_monitoring() before connection_setup() if you need popup handling
        during connect. stop_app() stops monitoring before shutting down the process.
        """
        self._do_bootstrap()
        ok = self._connection_service.launch_app()
        if ok:
            self._controller_connected = False
        return ok

    def did_start_app(self) -> bool:
        """True if the app was started by this script; False if it was already running (reused)."""
        return self._connection_service.did_launcher_start_app()

    def ensure_app_ready(self) -> bool:
        """
        Ensure application is running (launch if not). Use this; reserve 'connect' for API.
        Does not start message-box monitoring. Prefer `start()` for launch + msgbox + connect;
        or call start_msgbox_monitoring() before connection_setup() if you build the sequence manually.
        """
        self._do_bootstrap()
        ok = self._connection_service.ensure_app_ready()
        if ok:
            self._controller_connected = False
        return ok

    def get_base_url(self) -> str:
        """Base URL used for API calls after launch (usually http://127.0.0.1:port for local C2)."""
        return self._connection_service.get_base_url()

    def stop_app(self) -> dict:
        """Stop message-box monitoring first, then stop app, returning detailed status."""
        self.stop_msgbox_monitoring()
        self._msgbox_monitoring_started = False
        self._controller_connected = False
        return self._connection_service.stop_app_details()

    def is_connected(self) -> bool:
        """True if application is launched and running (local HTTP app is up)."""
        return self._connection_service.is_app_ready()

    def is_controller_connected(self) -> bool:
        """True after ConnectionSetup API reported success for this session."""
        return bool(self._controller_connected)

    def get_app_pid(self) -> Optional[int]:
        """PID for process started by launcher, or None when app was reused."""
        return self._connection_service.get_app_pid()

    def _collect_app_state(self) -> dict:
        """Collect common app fields used by start_app/connect payloads."""
        selected_app = self.get_selected_app()
        base_url = None
        controller_addr = None
        try:
            base_url = self.get_base_url()
        except Exception:
            base_url = None
        try:
            controller_addr = self.get_connection_address_from_config()
        except Exception:
            controller_addr = None
        return {
            "selectedApp": selected_app,
            "baseUrl": base_url,
            "controllerConnectionAddress": controller_addr,
        }

    def start_app(self) -> dict:
        """
        Start only the local C2 app process/server (no ConnectionSetup call).
        Returns basic app state for the next connect() step.
        """
        app_ready = bool(self.launch_app())
        started_by_launcher = bool(self.did_start_app())
        app_state = self._collect_app_state()
        return {
            "appStart": app_ready,
            "didLauncherStartApp": started_by_launcher,
            "pid": self.get_app_pid(),
            "selectedApp": app_state["selectedApp"],
            "baseUrl": app_state["baseUrl"],
            "controllerConnectionAddress": app_state["controllerConnectionAddress"],
            "timestamp": int(time.time()),
        }

    def connect(self) -> dict:
        """
        Keys in the returned dict:
          - appStart
          - didLauncherStartApp
          - selectedApp
          - baseUrl
          - controllerConnectionAddress
          - timestamp
          - connectionSetupSuccess
          - connectionSetupError
          - connectionSetup (full API result dict: success, resultType, error, data)
          - msgboxMonitoringStarted
        """
        if not self.is_connected():
            app_payload = self.start_app()
        else:
            app_state = self._collect_app_state()
            app_payload = {
                "appStart": True,
                "didLauncherStartApp": bool(self.did_start_app()),
                "pid": self.get_app_pid(),
                "selectedApp": app_state["selectedApp"],
                "baseUrl": app_state["baseUrl"],
                "controllerConnectionAddress": app_state["controllerConnectionAddress"],
                "timestamp": int(time.time()),
            }
        app_ready = bool(app_payload.get("appStart"))

        conn = Result.failure("App launch failed")
        if not app_ready:
            self._msgbox_monitoring_started = False
        else:
            self._msgbox_monitoring_started = bool(self.start_msgbox_monitoring())
            conn = self.connection_setup()
            if not conn.is_success:
                self.logger.warning(
                    "[connection] ConnectionSetup did not succeed (%s)",
                    conn.error or conn.result_type.value,
                )

        payload = {
            "appStart": app_payload.get("appStart"),
            "didLauncherStartApp": app_payload.get("didLauncherStartApp"),
            "pid": app_payload.get("pid"),
            "selectedApp": app_payload.get("selectedApp"),
            "baseUrl": app_payload.get("baseUrl"),
            "controllerConnectionAddress": app_payload.get("controllerConnectionAddress"),
            "connectionSetupSuccess": bool(app_ready and conn.is_success),
            "connectionSetupError": None if conn.is_success else conn.error,
            "connectionSetup": api_result_to_json_dict(conn),
            "timestamp": int(time.time()),
            "msgboxMonitoringStarted": bool(app_ready and self._msgbox_monitoring_started),
        }

        return payload

    def start(self) -> dict:
        """Backward-compatible one-shot wrapper: start_app() then connect()."""
        self.start_app()
        return self.connect()

    # ---- API calls (delegate to handler) ----
    def call_api(self, api_name: ApiName, **kwargs) -> ApiResult:
        """
        Call API by name (e.g. ApiName.CONNECTION_SETUP, ApiName.GET_TEST_CASE_LIST).
        Requires app to be launched first (launch_app or ensure_app_ready).
        kwargs: data=, params=, files= as needed by the endpoint.
        """
        from api.result import Result

        handler = self._connection_service.get_api_handler()
        if not handler:
            return Result.failure("App not launched; call launch_app() or ensure_app_ready() first")
        return handler.call_api(api_name, **kwargs)

    def get_connection_address_from_config(self) -> str:
        """
        Controller connection IP for GET /api/ConnectionSetup/0/<ip>.
        From applications.C2-EPR.ip_address (not the HTTP server host; base URL stays localhost).
        """
        if self._config_manager:
            ip = self._config_manager.get_app_field("ip_address", "127.0.0.1")
            if ip and isinstance(ip, str):
                return ip.strip()
        return "127.0.0.1"

    def connection_setup(self):
        """
        Connection setup: GET /api/ConnectionSetup/0/<connection_address>
        (e.g. http://localhost:5001/api/ConnectionSetup/0/192.0.2.50).
        """
        from api.result import Result

        handler = self._connection_service.get_api_handler()
        if not handler:
            self._controller_connected = False
            return Result.failure("App not launched; call launch_app() or ensure_app_ready() first")
        addr = self.get_connection_address_from_config()
        self.logger.info("[connection] ConnectionSetup: .../ConnectionSetup/0/%s", addr)
        result = handler.call_api(ApiName.CONNECTION_SETUP, path_suffix=addr)
        self._controller_connected = bool(result.is_success)
        return result

    # ---- Msgbox monitoring (separate thread, saves message/reply to JSON) ----
    def start_msgbox_monitoring(self):
        """
        Start the msgbox monitor thread (polls GetMessageBox, saves message and reply to JSON).
        Call after app launch. This can run before ConnectionSetup to catch early popups.
        """
        handler = self._connection_service.get_api_handler()
        if not handler:
            self._msgbox_monitoring_started = False
            self.logger.warning(
                "[msgbox] Cannot start: app not launched. Call launch_app() or ensure_app_ready() first."
            )
            return False
        if not hasattr(self, "_msgbox_framework") or self._msgbox_framework is None:
            from msgbox import MsgBoxFramework

            self._msgbox_framework = MsgBoxFramework(
                logger=self.logger,
                config_manager=self._config_manager,
            )
        self._msgbox_framework.set_api_handler(handler)
        self._msgbox_framework.start_monitoring()
        self._msgbox_monitoring_started = True
        self.logger.info(
            "[msgbox] Monitoring started; log file: %s", self._msgbox_framework.get_log_file_path()
        )
        return True

    def stop_msgbox_monitoring(self):
        """Stop the msgbox monitor thread and flush the log file."""
        self._msgbox_monitoring_started = False
        if hasattr(self, "_msgbox_framework") and self._msgbox_framework is not None:
            self._msgbox_framework.stop_monitoring()
            self.logger.info(
                "[msgbox] Monitoring stopped; log saved to: %s",
                self._msgbox_framework.get_log_file_path(),
            )
            return True
        return False

    # ---- Shared config helpers (used by mixins) ----
    def _get_common(self) -> dict:
        return self._config_manager.get_common() if self._config_manager else {}

    def _get_selected_app_key_for_state(self) -> str:
        """Selected app key for payloads."""
        return self._config_manager.get_selected_app() if self._config_manager else ""

    # ---- Reports framework ----
    def get_report_inputs(self) -> Dict[str, Any]:
        return self._report_framework.get_report_inputs()

    def update_report_inputs(self, report_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._report_framework.update_report_inputs(report_inputs=report_inputs)

    def get_test_run_info(self) -> Dict[str, Any]:
        return self._report_framework.get_test_run_info()

    def get_results_folder_name(self) -> Dict[str, Any]:
        return self._report_framework.get_results_folder_name()

    def get_report_file_name(self) -> Dict[str, Any]:
        return self._report_framework.get_report_file_name()

    def get_report_path_status(self) -> Dict[str, Any]:
        return self._report_framework.get_report_path_status()

    def build_report_url(self, report_file_name: Optional[str] = None) -> str:
        return self._report_framework.build_report_url(report_file_name=report_file_name)

    def run_report_flow(
        self,
        report_inputs: Optional[Dict[str, Any]] = None,
        *,
        copy_run_folder: bool = False,
    ) -> Dict[str, Any]:
        return self._report_framework.run_report_flow(
            report_inputs=report_inputs,
            copy_run_folder=copy_run_folder,
        )
