"""Test case list fetch, PostTestListToExecute, and run_testcases polling loop."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

from api import ApiName
from api.result import api_result_to_json_dict

from grlps_core.constants import (
    DEFAULT_DELAY_BETWEEN_API_STEPS_SECONDS,
    DEFAULT_PROGRESS_FULL_STATES_MAX,
    DEFAULT_STALL_TIMEOUT_SECONDS,
)
from grlps_core import test_results_progress as trp


class TestExecutionMixin:
    """
    Mixin: get_testcases_list, send_test_list, run_testcases.

    Requires: logger, call_api, _connection_service, _config_manager, _get_common,
    and ``_project_root()`` (provided by ``GRLPSApiClientCore``).
    """

    def get_testcases_list(self, save_to_disk: bool = True) -> dict:
        """
        Stage 2 - GetTestCaseList and extract leaf test case names.
        Saves:
          - test_case_list_raw.json
          - test_case_list.json
        under user_interaction/test_cases_list/...
        """
        from test_cases import TestCasesFramework

        delay = self._get_common().get("delayBetweenApiStepsSeconds", DEFAULT_DELAY_BETWEEN_API_STEPS_SECONDS)
        try:
            if delay is not None and float(delay) > 0:
                time.sleep(float(delay))
        except Exception:
            pass

        handler = self._connection_service.get_api_handler()
        if not handler:
            return {"success": False, "message": "App not launched; call start_app/connect first."}

        framework = TestCasesFramework(logger=self.logger, config_manager=self._config_manager)
        raw_data, names = (None, None)
        if save_to_disk:
            raw_data, names = framework.fetch_and_save(handler)
        else:
            from test_cases.test_cases_fetcher import fetch_test_cases

            raw_data, names = fetch_test_cases(handler)

        ok = names is not None and isinstance(names, list)
        payload = {
            "success": ok and (raw_data is not None or len(names or []) > 0),
            "testCaseCount": len(names or []),
        }
        if save_to_disk:
            payload["testCasesJsonPath"] = framework.get_file_path()
            payload["testCasesRawJsonPath"] = framework.get_raw_file_path()
            if payload["success"]:
                print(
                    f"  Test cases: {payload['testCaseCount']} names saved (list: {payload['testCasesJsonPath']}; raw: same folder)",
                    file=sys.stderr,
                    flush=True,
                )
        return payload

    def _get_known_test_names(self) -> Optional[List[str]]:
        """
        Names from the saved catalog, or None when it has not been fetched yet.

        None and an empty list mean different things here: None is "cannot
        check", which must not be treated as "nothing is valid".
        """
        try:
            from test_cases import TestCasesFramework

            path = TestCasesFramework(
                logger=self.logger, config_manager=self._config_manager
            ).get_file_path()
        except Exception:
            return None
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.logger.debug("[test_execution] Could not read test catalog %s: %s", path, e)
            return None
        if isinstance(data, list):
            return [str(x) for x in data]
        if isinstance(data, dict) and isinstance(data.get("testList"), list):
            return [str(x) for x in data["testList"]]
        return None

    def _get_test_list_to_execute_from_config(self) -> List[str]:
        common = self._get_common()
        path = common.get("testListToExecuteFile") or "config/test_list_to_execute.json"
        root = self._project_root()
        if not os.path.isabs(path):
            path = os.path.join(root, path)
        if not os.path.isfile(path):
            self.logger.debug("[test_execution] Test list file not found: %s", path)
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "testList" in data and isinstance(data["testList"], list):
                return data["testList"]
            return []
        except Exception as e:
            self.logger.warning("[test_execution] Failed to load test list from %s: %s", path, e)
            return []

    def send_test_list(self, test_list: Optional[List[str]] = None) -> dict:
        """
        Stage 2 - POST selected tests to execute (PostTestListToExecute).
        """
        try:
            if hasattr(self, "is_controller_connected") and not bool(self.is_controller_connected()):
                return {
                    "success": False,
                    "requestedCount": 0,
                    "message": "Controller is not connected. Call connect() and ensure connectionSetupSuccess=true before send_test_list().",
                }
        except Exception:
            pass

        resolved_list = test_list if test_list is not None else self._get_test_list_to_execute_from_config()
        if not isinstance(resolved_list, list):
            resolved_list = list(resolved_list) if resolved_list else []

        requested_count = len(resolved_list)
        if requested_count == 0:
            return {
                "success": False,
                "requestedCount": 0,
                "message": "No tests to execute (config test list empty/missing).",
            }

        # A name the controller does not know is accepted and then simply never
        # runs, which looks identical to a test that was skipped. Catch it here
        # while the catalog is on disk. Skipped when the catalog is absent.
        known = self._get_known_test_names()
        if known:
            unknown = [name for name in resolved_list if name not in set(known)]
            if unknown:
                return {
                    "success": False,
                    "requestedCount": requested_count,
                    "unknownTests": unknown,
                    "message": (
                        "{0} test name(s) are not in the test catalog for the loaded "
                        "VIF, so they would never run: {1}. Names must match exactly - "
                        "run c2epr-testcases (or load_vif) to refresh the catalog and "
                        "copy them from there.".format(len(unknown), ", ".join(unknown[:5]))
                    ),
                }

        post_res = self.call_api(ApiName.POST_TEST_LIST_TO_EXECUTE, data=resolved_list)
        payload = {
            "success": bool(post_res.is_success),
            "requestedCount": requested_count,
            "postTestListToExecute": api_result_to_json_dict(post_res),
            "error": post_res.error if not post_res.is_success else None,
        }
        if post_res.is_success:
            # Remember what is actually staged on the controller. run_testcases
            # reports progress against this; reading the config file there would
            # track a different set of tests whenever an explicit list is passed.
            self._staged_test_list = list(resolved_list)
            print(
                f"  Test list: {requested_count} test(s) sent to execute (PostTestListToExecute)",
                file=sys.stderr,
                flush=True,
            )
        return payload

    def run_testcases(
        self,
        timeout_sec: int = 15000,
        poll_interval_sec: float = 1.0,
        progress_full_states_max: int = DEFAULT_PROGRESS_FULL_STATES_MAX,
        progress_current_max_len: Optional[int] = None,
        progress_show_states: bool = True,
    ) -> dict:
        """
        Execute tests via POSTed list and poll GetAppState/GetTestResults for progress.

        Progress is logged with ``self.logger.info`` so log files get normal timestamps
        (same style as other ApiFramework lines). Default line is short and readable::

            [run_testcases] progress 3/4 (75.0%) | state=busy | current=... | elapsed=119s | eta=39s

        ``progress_show_states`` appends per-test ``states=...`` (small plans) or
        aggregate ``stats=...`` (large plans). ``current=`` uses a short label and is
        truncated only when ``progress_current_max_len`` is provided.
        """
        try:
            if hasattr(self, "is_controller_connected") and not bool(self.is_controller_connected()):
                return {
                    "success": False,
                    "completed": False,
                    "timedOut": False,
                    "stalled": False,
                    "message": "Controller is not connected. connect() failed, so run_testcases() is skipped.",
                }
        except Exception:
            pass

        # Track the list send_test_list actually posted. Falling back to the
        # config file is only right when no list was staged in this session -
        # otherwise an explicit send_test_list([...]) would be reported against
        # a different set of names, and the tests that really ran would be
        # filtered out of the progress display entirely.
        staged = getattr(self, "_staged_test_list", None)
        resolved_test_list = staged if staged else self._get_test_list_to_execute_from_config()
        expected_total = len(resolved_test_list) if isinstance(resolved_test_list, list) else 0
        expected_names = resolved_test_list if isinstance(resolved_test_list, list) else []
        progress_format_mode = (
            "full"
            if (expected_total > 0 and expected_total <= int(progress_full_states_max))
            else "compact"
        )
        common = self._get_common()
        stall_timeout_sec = float(DEFAULT_STALL_TIMEOUT_SECONDS)
        try:
            stall_timeout_sec = float(common.get("stallTimeoutSeconds", DEFAULT_STALL_TIMEOUT_SECONDS))
        except Exception:
            stall_timeout_sec = float(DEFAULT_STALL_TIMEOUT_SECONDS)

        start_ts = time.time()
        last_body = None
        last_app_state = None
        printed_started = False
        printed_finished = False
        last_progress = {
            "passCount": 0,
            "failCount": 0,
            "incompleteCount": 0,
            "otherCount": 0,
            "completed": 0,
            "total": expected_total,
            "percent": 0.0,
            "currentTest": None,
            "statesMap": {},
        }
        timed_out = False
        completed = False
        final_state = None
        last_print_completed = None
        last_print_current = None
        last_print_state = None
        last_print_ts = 0.0
        heartbeat_interval_sec = 1.0
        stalled = False
        ready_without_complete_results_since = None
        last_progress_change_ts = time.time()
        last_progress_signature = (
            int(last_progress.get("completed") or 0),
            str(last_progress.get("currentTest") or ""),
            int(last_progress.get("passCount") or 0),
            int(last_progress.get("failCount") or 0),
            int(last_progress.get("incompleteCount") or 0),
            str(last_app_state or ""),
        )
        get_test_results_fail_streak = 0
        last_plot_probe_ts = 0.0
        plot_probe_count = 0
        last_plot_probe = None

        def _probe_plot_running(now_ts: float) -> None:
            nonlocal last_plot_probe_ts, plot_probe_count, last_plot_probe
            # Diagnostic-only fallback:
            # Call GetAllChannelData only when GetTestResults is failing repeatedly.
            if (now_ts - last_plot_probe_ts) < 10.0:
                return
            last_plot_probe_ts = now_ts
            plot_probe_count += 1
            probe = self.call_api(
                ApiName.GET_ALL_CHANNEL_DATA,
                params={"startTime": 0, "stopTime": 0, "numberOfSamples": 2000},
            )
            probe_payload = api_result_to_json_dict(probe)
            last_plot_probe = {
                "timestamp": int(now_ts),
                "success": bool(probe_payload.get("success")),
                "error": probe_payload.get("error"),
            }
            if probe_payload.get("success"):
                self.logger.warning(
                    "[run_testcases] GetTestResults issue -> diagnostic GetAllChannelData succeeded (probe #%s)",
                    plot_probe_count,
                )
            else:
                self.logger.warning(
                    "[run_testcases] GetTestResults issue -> diagnostic GetAllChannelData failed (probe #%s): %s",
                    plot_probe_count,
                    probe_payload.get("error"),
                )

        while True:
            elapsed = time.time() - start_ts
            if elapsed > float(timeout_sec):
                timed_out = True
                break

            try:
                _ = self.call_api(ApiName.GET_APP_STATE)
            except Exception:
                pass

            tr_res = self.call_api(ApiName.GET_TEST_RESULTS)
            if tr_res.is_success:
                get_test_results_fail_streak = 0
                body = tr_res.value.get("response", {}).get("data", {}) or {}
                last_body = body

                app_status = body.get("appStatus") if isinstance(body, dict) else {}
                app_state = None
                if isinstance(app_status, dict):
                    app_state = app_status.get("appState") or app_status.get("app_state")
                last_app_state = app_state

                prog = trp.extract_test_progress(
                    body,
                    total_expected=expected_total or last_progress.get("total", 0),
                    expected_test_names=expected_names,
                )
                last_progress = prog
                current_signature = (
                    int(prog.get("completed") or 0),
                    str(prog.get("currentTest") or ""),
                    int(prog.get("passCount") or 0),
                    int(prog.get("failCount") or 0),
                    int(prog.get("incompleteCount") or 0),
                    str(app_state or ""),
                )
                if current_signature != last_progress_signature:
                    last_progress_signature = current_signature
                    last_progress_change_ts = time.time()

                should_print = False
                if prog.get("completed") != last_print_completed:
                    should_print = True
                if prog.get("currentTest") != last_print_current:
                    should_print = True
                if app_state != last_print_state:
                    should_print = True
                if app_state and str(app_state).upper() == "BUSY":
                    if (time.time() - last_print_ts) >= heartbeat_interval_sec:
                        should_print = True
                else:
                    if (time.time() - last_print_ts) >= 10.0:
                        should_print = True

                if should_print:
                    completed = True if app_state and str(app_state).upper() != "BUSY" else False
                    remaining = max(0.0, (prog["total"] - prog["completed"]))
                    eta_sec = None
                    if prog["completed"] > 0 and prog["total"] > 0 and prog["completed"] < prog["total"]:
                        eta_sec = elapsed * (remaining / prog["completed"])
                    else:
                        eta_sec = 0.0
                    eta_str = f"{eta_sec:.0f}s" if eta_sec is not None else "NA"
                    raw_cur = prog.get("currentTest") or "-"
                    max_len: Optional[int]
                    try:
                        max_len = (
                            int(progress_current_max_len)
                            if progress_current_max_len is not None
                            else None
                        )
                    except Exception:
                        max_len = None
                    if max_len is not None and max_len <= 0:
                        max_len = None
                    if isinstance(raw_cur, str) and raw_cur != "-":
                        short_cur = trp.short_label_expected_test(raw_cur)
                        cur = (
                            trp.truncate_progress_field(short_cur, max_len)
                            if max_len is not None
                            else short_cur
                        )
                    else:
                        cur = (
                            trp.truncate_progress_field(raw_cur, max_len)
                            if max_len is not None
                            else raw_cur
                        )
                    extra = ""
                    if progress_show_states:
                        sm = prog.get("statesMap") or {}
                        detail_frag, _ = trp.run_testcases_progress_detail(
                            prog,
                            sm,
                            expected_total,
                            int(progress_full_states_max),
                            expected_names=expected_names,
                        )
                        extra = f" | {detail_frag}"
                    st_low = str(app_state).lower() if app_state else "-"
                    self.logger.info(
                        "[run_testcases] progress %s/%s (%.1f%%) | state=%s | current=%s | elapsed=%ss | eta=%s%s",
                        prog["completed"],
                        prog["total"],
                        prog["percent"],
                        st_low,
                        cur,
                        f"{elapsed:.0f}",
                        eta_str,
                        extra,
                    )
                    last_print_completed = prog.get("completed")
                    last_print_current = prog.get("currentTest")
                    last_print_state = app_state
                    last_print_ts = time.time()

                if app_state and str(app_state).upper() != "BUSY":
                    if not printed_finished:
                        self.logger.info(
                            "[run_testcases] test execution finished (appState=%s); fetching GetTestResults",
                            str(app_state).lower() if app_state else "-",
                        )
                        printed_finished = True
                    completed = True
                    final_state = app_state

                    # App can flip to READY before GetTestResults is fully populated.
                    # Do a short settle loop so final pass/fail counts are not reported as 0/0.
                    settle_start = time.time()
                    settle_timeout_sec = max(3.0, float(poll_interval_sec) * 3.0)
                    while (time.time() - settle_start) < settle_timeout_sec:
                        time.sleep(min(1.0, max(0.2, float(poll_interval_sec))))
                        tr_settle = self.call_api(ApiName.GET_TEST_RESULTS)
                        if not tr_settle.is_success:
                            continue
                        settle_body = tr_settle.value.get("response", {}).get("data", {}) or {}
                        if settle_body is not None:
                            last_body = settle_body
                        settle_prog = trp.extract_test_progress(
                            settle_body,
                            total_expected=expected_total or last_progress.get("total", 0),
                            expected_test_names=expected_names,
                        )
                        if settle_prog:
                            last_progress = settle_prog
                            current_signature = (
                                int(settle_prog.get("completed") or 0),
                                str(settle_prog.get("currentTest") or ""),
                                int(settle_prog.get("passCount") or 0),
                                int(settle_prog.get("failCount") or 0),
                                int(settle_prog.get("incompleteCount") or 0),
                                str(app_state or ""),
                            )
                            if current_signature != last_progress_signature:
                                last_progress_signature = current_signature
                                last_progress_change_ts = time.time()
                        total_now = int(last_progress.get("total") or 0)
                        completed_now = int(last_progress.get("completed") or 0)
                        if total_now > 0 and completed_now >= total_now:
                            break

                    total_now = int(last_progress.get("total") or 0)
                    completed_now = int(last_progress.get("completed") or 0)
                    if total_now > 0 and completed_now < total_now:
                        # Some controllers flip to READY before final test states are
                        # written; keep polling for a grace window instead of exiting early.
                        if ready_without_complete_results_since is None:
                            ready_without_complete_results_since = time.time()
                            self.logger.warning(
                                "[run_testcases] appState=ready but results incomplete (%s/%s); continuing to poll",
                                completed_now,
                                total_now,
                            )
                        ready_wait_limit_sec = min(float(stall_timeout_sec), max(15.0, float(poll_interval_sec) * 15.0))
                        if (time.time() - ready_without_complete_results_since) < ready_wait_limit_sec:
                            completed = False
                            # Do not exit yet; continue polling loop.
                            time.sleep(float(poll_interval_sec))
                            continue
                    break
                if app_state and str(app_state).upper() == "BUSY" and not printed_started:
                    self.logger.info("[run_testcases] test execution started (appState=busy)")
                    printed_started = True
            else:
                get_test_results_fail_streak += 1
                if get_test_results_fail_streak >= 2:
                    _probe_plot_running(time.time())

            current_no_progress_sec = time.time() - last_progress_change_ts
            state_upper = str(last_app_state or "").upper()
            effective_stall_timeout_sec = (
                float(stall_timeout_sec) * 2.0 if state_upper == "BUSY" else float(stall_timeout_sec)
            )
            if current_no_progress_sec > effective_stall_timeout_sec:
                stalled = True
                self.logger.warning(
                    "[run_testcases] stalled: no progress for %.1fs (threshold=%.1fs); stopping run",
                    current_no_progress_sec,
                    effective_stall_timeout_sec,
                )
                break

            time.sleep(float(poll_interval_sec))

        duration = time.time() - start_ts
        if not final_state:
            final_state = last_app_state or ("READY" if not timed_out else "BUSY")

        test_results_saved_path = None
        try:
            create_get_test_results_json = bool(
                getattr(self, "create_get_test_results_json", False)
            )
            if create_get_test_results_json:
                common = self._get_common()
                log_dir = common.get("msgboxLogDir") or "user_interaction/logs"
                project_root = self._project_root()
                if not os.path.isabs(log_dir):
                    log_dir = os.path.join(project_root, log_dir)
                os.makedirs(log_dir, exist_ok=True)
                test_results_saved_path = os.path.join(log_dir, "test_results.json")
                if last_body is not None:
                    with open(test_results_saved_path, "w", encoding="utf-8") as f:
                        json.dump(last_body, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning("[test_execution] Could not save test_results.json: %s", e)

        ts_iso = datetime.now().isoformat(timespec="seconds")
        ts_unix = int(time.time())
        self.logger.info(
            "[run_testcases] run complete: pass=%s fail=%s incomplete=%s total=%s duration=%.1fs "
            "timestamp=%s timedOut=%s stalled=%s",
            last_progress["passCount"],
            last_progress["failCount"],
            last_progress["incompleteCount"],
            last_progress["total"],
            duration,
            ts_iso,
            timed_out,
            stalled,
        )

        total_for_completion = int(last_progress.get("total") or 0)
        completed_for_completion = int(last_progress.get("completed") or 0)
        has_expected_plan = total_for_completion > 0
        results_complete = (completed_for_completion >= total_for_completion) if has_expected_plan else completed
        ok = (not timed_out) and (not stalled) and bool(completed) and bool(results_complete)
        if test_results_saved_path:
            self.logger.info("[run_testcases] test results saved: %s", test_results_saved_path)
        progress_out = {k: v for k, v in last_progress.items() if k != "statesMap"}
        return {
            "success": bool(ok),
            "completed": bool(completed),
            "timedOut": bool(timed_out),
            "stalled": bool(stalled),
            "stallTimeoutSeconds": float(stall_timeout_sec),
            "finalState": final_state,
            "timestamp": ts_unix,
            "timestampIso": ts_iso,
            "durationSeconds": duration,
            "progress": progress_out,
            "progressFormat": progress_format_mode,
            "progressFullStatesMax": int(progress_full_states_max),
            "testResultsJsonPath": test_results_saved_path,
            "plotDiagnosticProbeCount": int(plot_probe_count),
            "lastPlotDiagnosticProbe": last_plot_probe,
        }
