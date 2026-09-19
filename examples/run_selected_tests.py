"""
Run a specific list of test cases, with everything passed explicitly.

Nothing here reads test_list_to_execute.json or common.selectedVifFile - the
VIF and the test names come from this file, which is what you want when one
script drives several devices.

    python examples/run_selected_tests.py

Set your controller IP in the workspace config first:
    c2epr-init        # prints the workspace path
"""
from __future__ import annotations

import sys

from grlps_api_client import GRLPSApiClient

# A VIF file name resolves inside the workspace's user_interaction/vif folder.
# An absolute path works too.
VIF_FILE = "example_captive_cable.xml"

PROJECT_NAME = "example-run"

# Names must match user_interaction/test_cases_list/test_case_list.json
# exactly. Run `c2epr-testcases` to regenerate that file for your VIF.
TEST_CASES = [
    "TEST.PD.PHY.ALL.1 Transmit Bit Rate and the Drift",
    "TEST.PD.PHY.ALL.2 Transmitter Eye Diagram",
]


def main() -> int:
    client = GRLPSApiClient()

    try:
        client.start_app()

        connect = client.connect()
        if not connect.get("connectionSetupSuccess"):
            print(
                "Connection failed: {0}".format(connect.get("connectionSetupError")),
                file=sys.stderr,
            )
            print(
                "Check applications.C2-EPR.ip_address in your workspace config.",
                file=sys.stderr,
            )
            return 1

        client.create_project(project_name=PROJECT_NAME)

        vif = client.load_vif(vif_file_path=VIF_FILE)
        print("VIF loaded: {0} test case(s) available".format(vif.get("testCaseCount")))

        client.send_test_list(test_list=TEST_CASES)

        # Blocks until the run finishes or timeout_sec elapses, printing
        # progress as each test changes state.
        run = client.run_testcases(timeout_sec=15000, poll_interval_sec=1.0)

        report = client.run_report_flow()
        print("Report: {0}".format(report.get("copiedReportPdf") or report))

        return 0 if run.get("success") else 1

    finally:
        # Always stop the app, including after an exception, so the next run
        # does not find it already running.
        client.stop_app()


if __name__ == "__main__":
    raise SystemExit(main())
