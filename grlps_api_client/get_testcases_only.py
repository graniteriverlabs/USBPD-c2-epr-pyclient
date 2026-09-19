"""
get_testcases_only.py — fetch the AVAILABLE test-case catalog WITHOUT running any tests.

Flow: start_app -> connect -> create_project -> load_vif (fetches GetTestCaseList) -> stop_app
Deliberately does NOT call send_test_list or run_testcases, so no test execution happens.

The available tests depend on the currently selected VIF (common.selectedVifFile),
so load_vif is required before the catalog can be fetched.

Run from repo root:
  python get_testcases_only.py

Result is written to: user_interaction/test_cases_list/test_case_list.json
"""
from __future__ import annotations

import sys
from grlps_api_client import GRLPSApiClient


def main() -> dict:
    client = GRLPSApiClient()
    try:
        client.start_app()

        connect = client.connect()
        if not bool(connect.get("connectionSetupSuccess")):
            print(
                f"[get_testcases_only] connect FAILED: {connect.get('connectionSetupError')}",
                file=sys.stderr,
                flush=True,
            )
            return {"success": False, "stage": "connect", "connect": connect}

        client.create_project()

        # load_vif() fetches + saves the test-case catalog (fetch_testcases_after=True default).
        vif = client.load_vif()

        count = int(vif.get("testCaseCount") or 0)
        path = vif.get("testCasesJsonPath")
        print(
            f"[get_testcases_only] DONE — {count} available test cases saved to: {path}",
            file=sys.stderr,
            flush=True,
        )
        return {
            "success": bool(vif.get("success")),
            "testCaseCount": count,
            "testCasesJsonPath": path,
            "testCasesRawJsonPath": vif.get("testCasesRawJsonPath"),
        }
    finally:
        client.stop_app()


def cli() -> int:
    """
    Console-script entry point.

    ``main`` returns the payload dict, which library callers rely on. A console
    script must hand back an int, so this wrapper maps the run onto a process
    exit code: 0 when the catalog was fetched, 1 otherwise.
    """
    return 0 if bool(main().get("success")) else 1


if __name__ == "__main__":
    raise SystemExit(cli())
