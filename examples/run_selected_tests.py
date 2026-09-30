r"""
Run a specific list of test cases, with everything passed explicitly.

Nothing here reads test_list_to_execute.json or common.selectedVifFile - the VIF
and the test names come from this file, which is what you want when one script
drives several devices.

Run it from a folder you have already set up:

    cd C:\benches\my-dut
    c2epr-init                          # once, to set the folder up
    python <path to>\run_selected_tests.py

The controller address and the report location can be set below or left to
config\grlps_app_config.json.
"""
from __future__ import annotations

import sys

from grlps_api_client import GRLPSApiClient, is_initialised, resolve_workspace

# A VIF file name resolves inside the workspace's user_interaction/vif folder.
# An absolute path works too.
VIF_FILE = "example_captive_cable.xml"

PROJECT_NAME = "example-run"

# Controller address. None uses applications.C2-EPR.ip_address from
# config\grlps_app_config.json. Set it here to drive a different controller
# without editing the config, which is what you want when one script runs
# against more than one bench.
IP_ADDRESS = None            # e.g. "192.0.2.50"

# Where exported reports are written. None uses common.reportExportDir. A
# relative path lands inside the workspace; an absolute path is used as given.
REPORT_EXPORT_DIR = None     # e.g. r"D:\reports\my-dut"

# Names must match user_interaction/test_cases_list/test_case_list.json
# exactly. Run `c2epr-testcases` to regenerate that file for your VIF.
TEST_CASES = [
    "TEST.PD.PHY.ALL.1 Transmit Bit Rate and the Drift",
    "TEST.PD.PHY.ALL.2 Transmitter Eye Diagram",
]


def main() -> int:
    workspace = resolve_workspace()
    if not is_initialised(workspace):
        print(
            "No GRLPS C2-EPR workspace in {0}\n"
            "Run 'c2epr-init' there first.".format(workspace),
            file=sys.stderr,
        )
        return 1

    # Anything left as None here falls back to the workspace config.
    client = GRLPSApiClient(
        ip_address=IP_ADDRESS,
        report_export_dir=REPORT_EXPORT_DIR,
    )

    try:
        client.start_app()

        connect = client.connect()
        if not connect.get("connectionSetupSuccess"):
            print(
                "Connection failed: {0}".format(connect.get("connectionSetupError")),
                file=sys.stderr,
            )
            print(
                "Tried {0} (from {1}). Set IP_ADDRESS in this script, or "
                "applications.C2-EPR.ip_address in your workspace config.".format(
                    connect.get("controllerConnectionAddress"),
                    connect.get("controllerConnectionAddressSource"),
                ),
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
