"""
GRLPS API Client — end-user facade.

Keep this file small and readable for customers. Runtime logic lives in
`grlps_api_client_core.GRLPSApiClientCore`.

Return value convention (for integrators)
-----------------------------------------
- Most methods return ``Dict[str, Any]`` suitable for ``json.dumps(...)``.
- Values are plain JSON-friendly types (dict, list, str, int, float, bool, None).
- Methods that wrap a single HTTP API (including report helpers below) use the
  **normalized API result** shape documented on ``call_api``.
"""
import os
import sys
from typing import Any, Dict, List, Optional

# If a release package contains runtime_internal_pyc, prefer those modules.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("GRLPS_API_PROJECT_ROOT", _THIS_DIR)
_RUNTIME_PYC = os.path.join(_THIS_DIR, "runtime_internal_pyc")
if os.path.isdir(_RUNTIME_PYC) and _RUNTIME_PYC not in sys.path:
    sys.path.insert(0, _RUNTIME_PYC)


# Oldest interpreter the client supports. Kept in step with requires-python in
# the packaging metadata, so pip and this check agree on what is allowed.
_MIN_PYTHON = (3, 11)


def _validate_runtime_requirements() -> None:
    """
    Enforce supported runtime for customer distribution:
    - OS: Windows
    - Python: 3.11 or newer
    """
    is_windows = os.name == "nt" or sys.platform.startswith("win")
    is_supported_py = sys.version_info[:2] >= _MIN_PYTHON
    current_py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    current_os = sys.platform
    expected = "Windows + Python {0}.{1} or newer".format(*_MIN_PYTHON)
    if is_windows and is_supported_py:
        print(
            "[grlps_api_init] Runtime check passed | expected: {0} | current: Python {1} on {2}".format(
                expected, current_py, current_os
            ),
            file=sys.stderr,
            flush=True,
        )
        return
    raise RuntimeError(
        "Incompatible Python runtime. GRLPS API Client requires {0}. ".format(expected)
        + 
        f"Current runtime: Python {current_py} on {current_os}."
    )


_validate_runtime_requirements()

from api import ApiName
from api.result import api_result_to_json_dict
from services.grlps_api_client_core import GRLPSApiClientCore, _DEFAULT_PROGRESS_FULL_STATES_MAX


class GRLPSApiClient:
    """
    Customer-facing API with JSON-friendly return values.

    Typical usage:
      1) start_app()
      2) connect()   # auto-starts app if needed
      3) workflow methods (create_project, load_vif, get_testcases_list,
         send_test_list, run_testcases, run_report_flow, …) and/or call_api(...)
      4) stop_app()

    All public methods that return a dict use ``Dict[str, Any]`` so outputs can be
    serialized with ``json.dumps(..., default=str)`` when needed.

    Configuration
    -------------
    **Customer release:** end users receive and edit **only**
    ``config/grlps_app_config.json`` (app EXE, port, controller IP, project/VIF
    paths, test list file, stall timeout, ``reportExportDir``, msgbox paths, …).

    **Internal (not for customer editing):** ``config/grlps_api_config.json`` (HTTP
    route map per ``ApiName``) and ``config/logging_config.json`` are kept inside
    the build (defaults / bytecode), not as separate customer deliverables.

    The two filenames differ by one word (**api** vs **app**) — confirm packaging
    with your release owner if docs and installers disagree. See
    ``GRLPSApiClient_USER_GUIDE.md``.
    """

    def __init__(self):
        """
        Construct the client using default config locations under the project root.

        Inputs: none (no constructor arguments for end users).

        Side effects: loads logging + app config, prepares connection service.
        """
        # End users should not pass config/logging file paths.
        self._core = GRLPSApiClientCore()

    def start_app(self) -> Dict[str, Any]:
        """
        Step 1 for end users: start only the local C2 app process/server.
        This method does not call ConnectionSetup.

        Inputs: none.

        Configuration source (customer file: `config/grlps_app_config.json`):
          - `selectedApp` (example: `"C2-EPR"`)
          - `applications.<selectedApp>`: `app_path`, `known_port`, `ip_address`
          - `common`: `initialWait`, `connectionTimeout`
          - `controllerConnectionAddress` in the return payload comes from
            `ip_address` and is used by `connect()`.

        Notes for end users:
          - Wrong EXE path, port, or IP: edit **`grlps_app_config.json`** (customer
            deliverable). HTTP route templates live in internal `grlps_api_config`
            and are not edited by customers.

        Returns (`Dict[str, Any]`):
          - appStart (`bool`): app process/server is running and API is reachable.
          - didLauncherStartApp (`bool`): True if this call started the process, False if already running.
          - pid (`int | None`): PID when this launcher started the app process; None if app was reused.
          - selectedApp (`str`): selected app name from config (example: "C2-EPR").
          - baseUrl (`str | None`): app API base URL (example: "http://127.0.0.1:5001").
          - controllerConnectionAddress (`str | None`): controller IP used later by connect().
          - timestamp (`int`): Unix epoch seconds when payload was created.
        """
        return self._core.start_app()

    def connect(self) -> Dict[str, Any]:
        """
        Step 2 for end users: run ConnectionSetup.
        If app is not running, this method calls start_app() internally first.

        Inputs: none.

        Configuration source (`config/grlps_app_config.json`):
          - `applications.<selectedApp>.ip_address` for ConnectionSetup path
          - `common.msgboxLogDir`, `common.msgboxLogJsonName` for popup log file

        Internal sequence:
          1) Ensure app is running (calls start_app() when needed)
          2) Start popup monitor (to auto-handle dialogs during connect)
          3) Call ConnectionSetup with configured controller IP
          4) Return normalized payload with summary booleans + full API result

        Notes for end users:
          - If `connectionSetupSuccess` is false, check:
              - `connectionSetupError`
              - `connectionSetup.data["response"]["data"]` for server-side details
          - Popup/log path: check `msgboxLogDir` / `msgboxLogJsonName` in
            **`grlps_app_config.json`**.
          - Wrong controller IP: update `ip_address` in **`grlps_app_config.json`**.

        Returns (`Dict[str, Any]`):
          - appStart (`bool`): app process/server ready for API calls.
          - didLauncherStartApp (`bool`): True if process was started in this flow.
          - pid (`int | None`): PID when launcher started app process; None if app was already running.
          - selectedApp (`str`): selected app name from config.
          - baseUrl (`str | None`): local API base URL.
          - controllerConnectionAddress (`str | None`): controller IP used in ConnectionSetup.
          - connectionSetupSuccess (`bool`): final ConnectionSetup pass/fail.
          - connectionSetupError (`str | None`): failure reason when setup fails.
          - connectionSetup (`Dict[str, Any]`): full normalized API result with keys:
              - success (`bool`)
              - resultType (`str`)  # "success" | "failure" | "warning"
              - error (`str | None`)
              - warning (`str | None`)
              - data (`Any`)        # request/response payload wrapper
          - timestamp (`int`)
          - msgboxMonitoringStarted (`bool`): popup monitor started before ConnectionSetup.
        """
        return self._core.connect()

    def stop_app(self) -> Dict[str, Any]:
        """
        Stop the local C2 app and internal popup monitor thread.

        Inputs: none.

        Returns (`Dict[str, Any]`):
          - success (`bool`): stop operation completed successfully.
          - alreadyStopped (`bool`): app was already not running for this client context.
          - stoppedByLauncher (`bool`): this client stopped a process it had launched.
          - externallyManagedRunning (`bool`): app is still running but was not owned by this launcher.
          - pid (`int | None`): launcher-managed process id when available.
          - message (`str`): human-readable stop status summary.
        """
        return self._core.stop_app()

    def is_connected(self) -> Dict[str, Any]:
        """
        Snapshot of local app readiness and controller session state.

        Inputs: none.

        Returns (``Dict[str, Any]``)::

            { "appReady": true | false, "controllerConnected": true | false }
        """
        return {
            "appReady": bool(self._core.is_connected()),
            "controllerConnected": bool(self._core.is_controller_connected()),
        }

    def call_api(self, api_name: ApiName, **kwargs) -> Dict[str, Any]:
        """
        Call a configured API endpoint by enum name.

        Inputs
        ------
        api_name : ApiName
            Endpoint name from ``api.api_enum.ApiName``.
        **kwargs (optional, endpoint-dependent)
            - ``data`` — request JSON body (``dict`` | ``list`` | ``None``).
            - ``params`` — query string parameters (``dict`` | ``None``).
            - ``files`` / multipart fields when the endpoint requires upload.
            - ``path_suffix`` — appended to the route (e.g. controller IP for
              ConnectionSetup, project name for PutProjectFolder).
            - ``vif_file_path`` — used by VIF upload helpers inside the handler.

        Returns (``Dict[str, Any]``) — normalized API result
        ----------------------------------------------------
        This is the standard wrapper around every low-level HTTP call::

            {
                "success": true | false,
                "resultType": "success" | "failure" | "warning",
                "error": "<string or null>",
                "warning": "<string or null>",
                "data": <server payload or null; often nested under response/data>
            }

        Server bodies vary by endpoint; inspect ``data`` for the raw structure.

        Examples
        --------
        - ``client.call_api(ApiName.GET_SOFTWARE_VERSION)``
        - ``client.call_api(ApiName.GET_APP_STATE)``
        - ``client.call_api(ApiName.GET_TEST_CASE_LIST, path_suffix="APP")``

        Route templates are loaded from internal ``grlps_api_config`` (not a
        customer-edited file). Requires ``start_app()`` then ``connect()`` (or
        equivalent) before use.
        """
        return api_result_to_json_dict(self._core.call_api(api_name, **kwargs))

    # ---- Stage 2: project + VIF loading ----
    def create_project(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create / set the project folder name on the application (PutProjectFolder).

        Inputs
        ------
        project_name : str | None
            Folder name to send. If omitted, uses ``common.projectName`` in
            ``config/grlps_app_config.json``.

        Returns (``Dict[str, Any]``)
        ----------------------------
        Success path::

            {
                "success": true,
                "projectName": "<resolved name>",
                "putProjectFolder": { ... normalized API result (call_api shape) ... }
            }

        Failure (missing name)::

            {
                "success": false,
                "projectName": null,
                "message": "<reason>"
            }
        """
        return self._core.create_project(project_name=project_name)

    def load_vif(
        self,
        vif_file_path: Optional[str] = None,
        *,
        fetch_testcases_after: bool = True,
        testcases_save_to_disk: bool = True,
    ) -> Dict[str, Any]:
        """
        Load a VIF XML: convert to JSON, upload file, PutVIFData, PutPortConfigurations.

        After all VIF HTTP steps succeed, by default the client also calls
        ``get_testcases_list`` so the received test list JSON is created on disk
        without a separate method call. Disable with ``fetch_testcases_after=False``.

        Inputs
        ------
        vif_file_path : str | None
            Path to the VIF XML file, or a name relative to ``common.vifDir`` in
            ``grlps_app_config.json``. If omitted, uses ``common.selectedVifFile``.
        fetch_testcases_after : bool
            When ``True`` (default), run ``get_testcases_list`` after a successful VIF load.
        testcases_save_to_disk : bool
            Passed through to ``get_testcases_list`` when the post-load fetch runs.

        Returns (``Dict[str, Any]``)
        ----------------------------
        On success (VIF HTTP steps OK), when ``fetch_testcases_after`` is ``True`` (default),
        the same fields ``get_testcases_list`` would return are merged into this dict::

            {
                "success": true,
                "vifFilePath": "<absolute path>",
                "vifFileName": "<base name>",
                "convertedVifJsonPath": "<path or null if save failed>",
                "putVIFFile": { ... call_api shape ... },
                "putVIFFileAttempt": "filename-only" | "multipart",
                "putVIFData": { ... call_api shape ... },
                "putPortConfigurations": { ... call_api shape ... },
                "testCasesListSuccess": true,
                "testCaseCount": <int>,
                "testCasesJsonPath": "<path when testcases_save_to_disk>",
                "testCasesRawJsonPath": "<path when testcases_save_to_disk>",
                "testCasesListMessage": "<only when list fetch failed or unavailable; reason>"
            }

        Top-level ``success`` is the VIF upload/configuration outcome. ``testCasesListSuccess``
        mirrors ``get_testcases_list`` ``success``. If the list fetch fails after VIF succeeds,
        ``success`` stays ``true`` and ``testCasesListSuccess`` is ``false``.

        Test-case keys are omitted when ``fetch_testcases_after`` is ``False``, or when the
        VIF load fails before those steps complete.

        On failure (file missing, XML parse error, etc.)::

            {
                "success": false,
                "vifFilePath": "<path or null>",
                "message": "<reason>"
            }
        """
        return self._core.load_vif(
            vif_file_path=vif_file_path,
            fetch_testcases_after=fetch_testcases_after,
            testcases_save_to_disk=testcases_save_to_disk,
        )

    # ---- Test cases + execution ----
    def get_testcases_list(self, save_to_disk: bool = True) -> Dict[str, Any]:
        """
        Fetch the test case tree from the app and extract runnable test names.

        **Optional** when you already called ``load_vif`` with default
        ``fetch_testcases_after=True`` (list is then fetched and saved there).
        Use this method to **refresh** the list without reloading the VIF.

        Inputs
        ------
        save_to_disk : bool
            If true (default), writes raw and flat list JSON under
            ``user_interaction/test_cases_list/`` (paths from config).

        Returns (``Dict[str, Any]``)
        ----------------------------
        Typical success::

            {
                "success": true,
                "testCaseCount": <int>,
                "testCasesJsonPath": "<path when save_to_disk>",
                "testCasesRawJsonPath": "<path when save_to_disk>"
            }

        When ``save_to_disk`` is false, path keys are omitted.

        Failure::

            { "success": false, "message": "<reason>" }
        """
        return self._core.get_testcases_list(save_to_disk=save_to_disk)

    def send_test_list(self, test_list: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        POST the list of tests to execute (PostTestListToExecute).

        Inputs
        ------
        test_list : list[str] | None
            Explicit test names. If omitted, loads the file named by
            ``common.testListToExecuteFile`` in ``grlps_app_config.json`` (JSON array
            or ``{"testList": [...]}``).

        Returns (``Dict[str, Any]``)
        ----------------------------
        ::

            {
                "success": true | false,
                "requestedCount": <int>,
                "postTestListToExecute": { ... call_api shape ... },
                "error": "<string or null if success>"
            }

        If the controller is not connected or the list is empty, ``success`` is
        false and ``message`` explains why.
        """
        return self._core.send_test_list(test_list=test_list)

    def run_testcases(
        self,
        timeout_sec: int = 15000,
        poll_interval_sec: float = 1.0,
        progress_full_states_max: int = _DEFAULT_PROGRESS_FULL_STATES_MAX,
        progress_current_max_len: Optional[int] = None,
        progress_show_states: bool = True,
    ) -> Dict[str, Any]:
        """
        Poll test execution until finished, timeout, or stall (no progress).

        Inputs
        ------
        timeout_sec : int
            Maximum seconds to wait for the run to finish.
        poll_interval_sec : float
            Delay between GetTestResults (and related) polls.
        Test list must be posted first via ``send_test_list()`` before this call.
        progress_full_states_max : int
            When expected test count is at or below this, progress format is
            considered "full"; otherwise "compact".
        progress_current_max_len : int | None
            Max length of the logged ``current=`` test label. If ``None``,
            test names are not truncated.
        progress_show_states : bool
            If true (default), append extra per-test state detail to progress log lines.

        Stall detection uses ``common.stallTimeoutSeconds`` in
        ``grlps_app_config.json`` (default 300); while ``appState`` is BUSY the
        effective threshold is doubled.

        Returns (``Dict[str, Any]``)
        ----------------------------
        ::

            {
                "success": true | false,
                "completed": true | false,
                "timedOut": true | false,
                "stalled": true | false,
                "stallTimeoutSeconds": <float from config>,
                "finalState": "<last app state string>",
                "timestamp": <unix seconds>,
                "timestampIso": "<ISO8601 local>",
                "durationSeconds": <float>,
                "progress": {
                    "passCount", "failCount", "incompleteCount", "otherCount",
                    "completed", "total", "percent", "currentTest"
                },
                "progressFormat": "full" | "compact",
                "progressFullStatesMax": <int>,
                "testResultsJsonPath": "<path or null; only if debug flag enabled>",
                "plotDiagnosticProbeCount": <int>,
                "lastPlotDiagnosticProbe": { "timestamp", "success", "error" } | null
            }

        ``success`` is true only when the run finished without timeout or stall
        and results look complete for the expected plan.
        """
        return self._core.run_testcases(
            timeout_sec=timeout_sec,
            poll_interval_sec=poll_interval_sec,
            progress_full_states_max=progress_full_states_max,
            progress_current_max_len=progress_current_max_len,
            progress_show_states=progress_show_states,
        )

    # ---- Report framework ----
    # Optional low-level report APIs below. For the normal post-test flow, call
    # ``run_report_flow()`` only; it runs these steps and export together.
    def get_report_inputs(self) -> Dict[str, Any]:
        """
        GET current report input fields (ReportsGeneration/GetReportInputs).

        Optional building block. Prefer ``run_report_flow()`` unless you are
        assembling a custom report sequence.

        Inputs: none.

        Returns: normalized API result dict (see ``call_api``).
        """
        return self._core.get_report_inputs()

    def update_report_inputs(self, report_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        POST updated report input fields (ReportsGeneration/PostUpdateReportInputs).

        Inputs
        ------
        report_inputs : dict | None
            Key/value map to send as JSON body. Use ``{}`` or omit to post an
            empty object.

        Returns: normalized API result dict (see ``call_api``).
        """
        return self._core.update_report_inputs(report_inputs=report_inputs)

    def get_test_run_info(self) -> Dict[str, Any]:
        """
        GET historical / available test run folders (GetTestRunInfo).

        Inputs: none.

        Returns: normalized API result dict. When successful, ``data`` typically
        contains a list of objects with fields such as ``resultsFolder``,
        ``folderSize``, ``creationDateTime`` (exact keys depend on server).
        """
        return self._core.get_test_run_info()

    def get_results_folder_name(self) -> Dict[str, Any]:
        """
        GET active results folder name for the current report run.

        Inputs: none.

        Returns: normalized API result dict; inner ``data`` is often a string
        folder name (e.g. ``Demo_2026_03_27-22_41_35``).
        """
        return self._core.get_results_folder_name()

    def get_report_file_name(self) -> Dict[str, Any]:
        """
        GET generated report HTML file name (GetReportFileName).

        Inputs: none.

        Returns: normalized API result dict; inner ``data`` is often the HTML
        file name (e.g. ``GRL_USB_PD_Report_Run_1_2026_03_27.html``).
        """
        return self._core.get_report_file_name()

    def get_report_path_status(self) -> Dict[str, Any]:
        """
        GET report path health (GetReportPathStatus).

        Inputs: none.

        Returns: normalized API result dict (may be empty on some builds).
        """
        return self._core.get_report_path_status()

    def build_report_url(self, report_file_name: Optional[str] = None) -> str:
        """
        Build the browser URL for the report HTML served by the local app.

        Inputs
        ------
        report_file_name : str | None
            File name only (e.g. ``....html``). If omitted, calls
            ``get_report_file_name()`` internally.

        Returns
        -------
        str
            ``"{baseUrl}/Report/{file}"`` or ``""`` if base URL or name missing.
        """
        return self._core.build_report_url(report_file_name=report_file_name)

    def run_report_flow(
        self,
        report_inputs: Optional[Dict[str, Any]] = None,
        *,
        copy_run_folder: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the full report workflow: update inputs, query report APIs, export artifacts.

        This is the **standard** report step after ``run_testcases``; you do not
        need to call ``get_report_inputs``, ``get_test_run_info``, etc. separately
        unless you replace part of this flow.

        Inputs
        ------
        report_inputs : dict | None
            Optional map passed to ``update_report_inputs`` (same as POST body).
        copy_run_folder : bool
            When ``True``, also copy the entire run folder under destination.
            Default ``False`` copies only HTML/PDF files.

        Returns (``Dict[str, Any]``) — consolidated payload
        --------------------------------------------------
        ::

            {
                "updateReportInputs": { ... call_api shape ... },
                "getReportInputs": { ... },
                "getTestRunInfo": { ... },
                "getResultsFolderName": { ... },
                "getReportFileName": { ... },
                "getReportPathStatus": { ... },
                "reportUrl": "<http://host:port/Report/....html or \"\">",
                "reportExport": {
                    "enabled": true,
                    "success": true | false,
                    "destination": "<export root>",
                    "requestedDestination": "<common.reportExportDir from grlps_app_config>",
                    "sourceFolder": "<actual folder used, e.g. New_Run...>",
                    "resolvedRunFolder": "<parent Demo_... run folder>",
                    "copiedRunFolder": "<folder under destination>",
                    "copiedReportHtml": "<path or null>",
                    "copiedReportPdf": "<path or null>",
                    "message": "<summary>"
                },
                "reportSourceFolder": "<same as reportExport.sourceFolder>",
                "reportRunRootFolder": "<same as reportExport.resolvedRunFolder>",
                "reportDataHint": "<static guidance string>",
                "timestamp": <unix seconds>
            }

        Export destination comes from ``common.reportExportDir`` in
        **``grlps_app_config.json``**; invalid paths fall back to
        ``user_interaction/reports_export`` when needed.
        """
        return self._core.run_report_flow(
            report_inputs=report_inputs,
            copy_run_folder=copy_run_folder,
        )
