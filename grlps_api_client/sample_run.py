"""
sample_run.py — end-to-end demo:
  start_app -> connect -> create_project -> load_vif (includes test case list fetch) ->
  send_test_list -> run_testcases -> run_report_flow -> stop_app
  (If connect fails, stop_app and return early — see main().)

Run from this repo root:
  python sample_run.py

End-user documentation: GRLPSApiClient_USER_GUIDE.md
"""

from __future__ import annotations

import json
import sys
from grlps_api_client import GRLPSApiClient

VERBOSE_PAYLOADS = False


def _print_payload(step_name: str, payload) -> None:
    if not VERBOSE_PAYLOADS:
        return
    print(f"{step_name} response:", file=sys.stderr, flush=True)
    print(json.dumps(payload, indent=2, ensure_ascii=False), file=sys.stderr, flush=True)


def main() -> dict:
    client = GRLPSApiClient()
    start_payload = client.start_app()
    _print_payload("start_app", start_payload)
    connect_payload = client.connect()
    _print_payload("connect", connect_payload)
    if not bool(connect_payload.get("connectionSetupSuccess")):
        client.stop_app()
        return {"start_app": start_payload, "connect": connect_payload}

    # create_project defaults:
    #   project_name=None -> uses common.projectName from grlps_app_config.json
    # Example explicit input (reference only):
    # create_project_payload = client.create_project(project_name="Demo")
    create_project_payload = client.create_project()
    _print_payload("create_project", create_project_payload)

    # load_vif defaults:
    #   vif_file_path=None -> uses common.selectedVifFile in common.vifDir
    #   fetch_testcases_after=True
    #   testcases_save_to_disk=True
    # Example explicit input (reference only):
    # load_vif_payload = client.load_vif(vif_file_path="my_device.xml")
    # Single call: VIF load + received test list (paths/count on same dict as VIF result).
    load_vif_payload = client.load_vif()
    _print_payload("load_vif", load_vif_payload)

    # Stop here if the VIF did not load. Without this the run continues against
    # whatever VIF the application already had loaded, and every test comes back
    # inconclusive with nothing to say why.
    if not bool(load_vif_payload.get("success")):
        print(
            "[sample_run] VIF load FAILED: {0}".format(
                load_vif_payload.get("message") or "see log"
            ),
            file=sys.stderr,
            flush=True,
        )
        client.stop_app()
        return {
            "start_app": start_payload,
            "connect": connect_payload,
            "create_project": create_project_payload,
            "load_vif": load_vif_payload,
        }

    # A VIF that loads but yields no test cases is also unrunnable - usually the
    # VIF does not describe the device that is actually connected.
    if not int(load_vif_payload.get("testCaseCount") or 0):
        print(
            "[sample_run] VIF loaded but reports 0 test cases - check that "
            "common.selectedVifFile matches the connected device.",
            file=sys.stderr,
            flush=True,
        )
        client.stop_app()
        return {
            "start_app": start_payload,
            "connect": connect_payload,
            "create_project": create_project_payload,
            "load_vif": load_vif_payload,
        }

    # send_test_list defaults:
    #   test_list=None -> uses common.testListToExecuteFile from grlps_app_config.json
    # Example explicit input (reference only):
    # send_test_list_payload = client.send_test_list(test_list=["TC1", "TC2"])
    send_test_list_payload = client.send_test_list()
    _print_payload("send_test_list", send_test_list_payload)

    # If the list was not accepted, nothing is staged on the controller and the
    # run below would poll an idle instrument and report every test as
    # NOT_EXECUTED, with no indication that the cause was here.
    if not bool(send_test_list_payload.get("success")):
        print(
            "[sample_run] test list REJECTED: {0}".format(
                send_test_list_payload.get("message") or "see log"
            ),
            file=sys.stderr,
            flush=True,
        )
        client.stop_app()
        return {
            "start_app": start_payload,
            "connect": connect_payload,
            "create_project": create_project_payload,
            "load_vif": load_vif_payload,
            "send_test_list": send_test_list_payload,
        }

    # Example with explicit inputs (reference only):
    # Defaults:
    #   timeout_sec=15000
    #   poll_interval_sec=1.0
    #   progress_show_states=True
    #   progress_current_max_len=None (full testcase name; no truncation)
    #   progress_full_states_max=32
    # run_testcases_payload = client.run_testcases(
    #     timeout_sec=15000,
    #     poll_interval_sec=1.0,
    #     progress_full_states_max=32,
    #     progress_show_states=True,
    #     progress_current_max_len=None,
    # )
    run_testcases_payload = client.run_testcases()
    _print_payload("run_testcases", run_testcases_payload)

    # The report is still generated below when the run falls short, because a
    # partial report is usually worth having - but say plainly what happened,
    # since the controller itself reports nothing when it declines to run a test.
    if not bool(run_testcases_payload.get("success")):
        print(
            "[sample_run] run did NOT complete: {0}".format(
                run_testcases_payload.get("message") or "see log"
            ),
            file=sys.stderr,
            flush=True,
        )

    # run_report_flow defaults:
    #   report_inputs=None
    #   copy_run_folder=False (copies only HTML/PDF)
    # Example explicit input (reference only):
    # report_payload = client.run_report_flow(report_inputs={}, copy_run_folder=False)
    report_payload = client.run_report_flow()
    _print_payload("run_report_flow", report_payload)

    stop_payload = client.stop_app()
    _print_payload("stop_app", stop_payload)
    out = {
        "start_app": start_payload,
        "connect": connect_payload,
        "create_project": create_project_payload,
        "load_vif": load_vif_payload,
        "send_test_list": send_test_list_payload,
        "run_testcases": run_testcases_payload,
        "run_report_flow": report_payload,
        "stop_app": stop_payload,
    }
    return out


def cli() -> int:
    """
    Console-script entry point.

    ``main`` returns the payload dict, which library callers rely on. A console
    script must hand back an int, so this wrapper maps the run onto a process
    exit code: 0 when the flow ran to completion, 1 when it stopped early.

    ``main`` returns a short dict when it bails out, so the absence of a step is
    itself the signal that the step never happened.
    """
    result = main()

    connect = result.get("connect") or {}
    if not bool(connect.get("connectionSetupSuccess")):
        print(
            "[sample_run] connect FAILED - no tests were run.",
            file=sys.stderr,
            flush=True,
        )
        return 1

    if "run_testcases" not in result:
        print(
            "[sample_run] stopped before running tests - see the message above.",
            file=sys.stderr,
            flush=True,
        )
        return 1

    # A run that executed nothing must not report success to a CI job.
    if not bool((result.get("run_testcases") or {}).get("success")):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
