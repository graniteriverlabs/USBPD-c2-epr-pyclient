r"""
List the test cases a VIF makes available, without running anything.

The catalog depends on the VIF, so the VIF has to be loaded first. No test is
executed by this script.

Run it from a folder you have already set up:

    cd C:\benches\my-dut
    c2epr-init                          # once, to set the folder up
    python <path to>\fetch_test_catalog.py
    python <path to>\fetch_test_catalog.py MyDevice.xml

`c2epr-testcases` does the same thing as a single command; this script is here
to show the calls behind it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from grlps_api_client import GRLPSApiClient, is_initialised, resolve_workspace

DEFAULT_VIF = "example_captive_cable.xml"


def main() -> int:
    workspace = resolve_workspace()
    if not is_initialised(workspace):
        print(
            "No GRLPS C2-EPR workspace in {0}\n"
            "Run 'c2epr-init' there first.".format(workspace),
            file=sys.stderr,
        )
        return 1

    vif_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VIF
    client = GRLPSApiClient()

    try:
        client.start_app()

        connect = client.connect()
        if not connect.get("connectionSetupSuccess"):
            print(
                "Connection failed: {0}".format(connect.get("connectionSetupError")),
                file=sys.stderr,
            )
            return 1

        client.create_project()

        # load_vif fetches and saves the catalog by default
        # (fetch_testcases_after=True).
        vif = client.load_vif(vif_file_path=vif_file)

        catalog_path = vif.get("testCasesJsonPath")
        print("{0} test case(s) available for {1}".format(vif.get("testCaseCount"), vif_file))
        print("Saved to: {0}".format(catalog_path))

        if catalog_path and Path(catalog_path).is_file():
            names = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
            print()
            for name in names[:20]:
                print("  {0}".format(name))
            if len(names) > 20:
                print("  ... and {0} more".format(len(names) - 20))
            print()
            print("Copy the names you want into config/test_list_to_execute.json")

        return 0 if vif.get("success") else 1

    finally:
        client.stop_app()


if __name__ == "__main__":
    raise SystemExit(main())
