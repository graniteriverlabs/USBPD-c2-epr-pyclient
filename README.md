# GRLPS C2-EPR API Client

Python client for the **GRL Platform Solutions (GRLPS) USB-PD C2-EPR** application. It drives the app over
its local HTTP API: start it, connect to the controller, load a VIF, pick test
cases, run them and collect the report — from a script or from the command line.

```python
from grlps_api_client import GRLPSApiClient

client = GRLPSApiClient()
client.start_app()
client.connect()
client.load_vif("MyDevice.xml")
client.run_testcases()
```

## Requirements

| | |
|---|---|
| OS | Windows |
| Python | 3.11 or newer (enforced at install and at import) |
| Software | GRLPS USB-PD C2-EPR application, installed and licensed |
| Hardware | a reachable GRLPS C2-EPR controller |

## Install

You do **not** need to clone this repository.

```powershell
pip install https://github.com/graniteriverlabs/USBPD-c2-epr-pyclient/releases/download/v1.6.1.2/usbpd_c2_epr_pyclient-1.6.1.2-py3-none-any.whl
```

Or install the latest source directly:

```powershell
pip install git+https://github.com/graniteriverlabs/USBPD-c2-epr-pyclient.git
```

> **Names:** the distribution is `usbpd-c2-epr-pyclient`; the module you import is
> `grlps_api_client`. The import name is deliberately unchanged so existing
> scripts keep working.

## Quickstart

### 1. Create your workspace

Make a folder for this bench or project, and initialise it there:

```powershell
mkdir C:\benches\my-dut
cd C:\benches\my-dut
c2epr-init
```

`c2epr-init` copies the default config into **the directory you are standing
in**, then prints what still needs setting.

Run `c2epr-testcases` and `c2epr-run` from this same directory. One folder
drives as many devices as you like — keep every VIF in `user_interaction\vif\`
and switch with `selectedVifFile`, or pass one per run in code with
`load_vif("Other.xml")`. Use a second folder only when you want a second set of
settings.

Your edits are never overwritten — re-running `c2epr-init` only restores files
that are missing, so upgrades keep your settings. The same rule means a
corrected default cannot reach a folder you already have: when a shipped
config file has moved on, the client says so at run time and names the file to
delete before re-running `c2epr-init`.

### 2. Set your controller address

Open `config\grlps_app_config.json` in that folder and replace the placeholder:

```json
"ip_address": "192.0.2.50"     →     "ip_address": "<your controller IP>"
```

Check `app_path` points at your GRLPS C2-EPR installation while you are there.

A script can supply the address instead, which is what you want when one
script drives more than one controller:

```python
client = GRLPSApiClient(ip_address="<your controller IP>")
```

### 3. Add your VIF

Copy your VIF XML into the workspace and select it:

```powershell
copy C:\path\to\MyDevice.xml user_interaction\vif\
```

```json
"selectedVifFile": "MyDevice.xml"
```

A generic `example_captive_cable.xml` ships with the package so the flow runs
before you supply your own.

### 4. See which tests your VIF supports

```powershell
c2epr-testcases
```

The available tests depend on the VIF, so this loads the VIF first. It writes
every runnable test name to:

```
user_interaction\test_cases_list\test_case_list.json
```

No tests are executed by this command.

### 5. Choose the tests to run

Edit `config\test_list_to_execute.json` — a plain list of names:

```json
[
  "TEST.PD.PHY.ALL.1 Transmit Bit Rate and the Drift",
  "TEST.PD.PHY.ALL.2 Transmitter Eye Diagram"
]
```

> Copy and paste the names. A name the application does not know is rejected
> before the run starts and the offending entries are listed, so nothing runs
> against a half-correct list. A name that differs only in leading or trailing
> spaces is corrected to the application's own spelling and reported — at
> least one C2-EPR test name really does end in a space.

### 6. Run

```powershell
c2epr-run
```

Start app → connect → create project → load VIF → send test list → run → report
→ stop app. Exit code `0` means the run connected and completed.

## Commands

| Command | Does |
|---|---|
| `c2epr-init` | create/inspect the workspace, report what is unconfigured |
| `c2epr-testcases` | fetch the available test list for the selected VIF |
| `c2epr-run` | run the full end-to-end flow |

All three return `0` on success and `1` on failure, so they drop straight into CI.

## Using it from Python

Every setting can come from the config file **or** from your code. The config
file suits a fixed bench; arguments suit a script that varies per run.

Every method returns a `dict` with a `success` flag rather than raising, so
check each step — a failed VIF load otherwise lets the run continue against
whatever the application had loaded before.

```python
from grlps_api_client import GRLPSApiClient

# Anything omitted here comes from config\grlps_app_config.json.
client = GRLPSApiClient(
    ip_address="192.0.2.50",
    report_export_dir=r"D:\reports\my-dut",
)
try:
    client.start_app()

    connect = client.connect()
    if not connect.get("connectionSetupSuccess"):
        raise SystemExit("controller not reachable: {0}".format(
            connect.get("connectionSetupError")))

    client.create_project("MyProject")

    vif = client.load_vif("MyDevice.xml")
    if not vif.get("success"):
        raise SystemExit("VIF not loaded: {0}".format(vif.get("message")))
    print("{0} test cases available".format(vif.get("testCaseCount")))

    sent = client.send_test_list([
        "TEST.PD.PHY.ALL.1 Transmit Bit Rate and the Drift",
    ])
    if not sent.get("success"):
        raise SystemExit("test list rejected: {0}".format(sent.get("message")))

    run = client.run_testcases()
    report = client.run_report_flow()
    print("report:", report.get("reportExport", {}).get("destination"))
finally:
    client.stop_app()
```

| Setting | Config file | In code |
|---|---|---|
| VIF | `common.selectedVifFile` | `client.load_vif("x.xml")` |
| Tests | `config/test_list_to_execute.json` | `client.send_test_list([...])` |
| Project name | `common.projectName` | `client.create_project("Name")` |
| Controller IP | `applications.<app>.ip_address` | `GRLPSApiClient(ip_address=...)` or `client.connect(ip_address=...)` |
| Report location | `common.reportExportDir` | `GRLPSApiClient(report_export_dir=...)` or `client.run_report_flow(report_export_dir=...)` |

For the last two the order is: the argument to the call, then the one given to
`GRLPSApiClient(...)`, then the config file. Leave a value out, or pass `None`
or `""`, and the next one down is used — so a script that sets neither behaves
exactly as it always has. A relative `report_export_dir` lands inside the
workspace, the same as the config value does. `connect()` reports which of the
three supplied the address in `controllerConnectionAddressSource`.

Every method returns a JSON-serialisable `dict`. See
[`examples/`](examples/) for complete scripts, and the
[user guide](grlps_api_client/docs/GRLPSApiClient_USER_GUIDE.md) for the full
method reference.

## The workspace

Everything lives in the directory where you ran `c2epr-init`:

```
your-project-folder\
├── config\
│   ├── grlps_app_config.json       IP, VIF choice, timeouts, paths
│   ├── test_list_to_execute.json   which tests to run
│   ├── grlps_api_config.json       API endpoint map (leave alone)
│   ├── logging_config.json
│   └── put_port_config_mapping.json   device type → cable selection
└── user_interaction\
    ├── vif\                        put your VIF files here
    ├── test_cases_list\            generated: available tests
    ├── reports_export\             generated: one subfolder per run
    └── logs\                       generated: session + app logs
```

To run the commands from somewhere else, point them at the folder:

```powershell
set GRLPS_API_PROJECT_ROOT=C:\benches\my-dut
```

| Variable | Effect |
|---|---|
| `GRLPS_API_PROJECT_ROOT` | use this folder as the workspace, wherever you run from |
| `GRLPS_API_HOME` | where `c2epr-init` creates the workspace, instead of the current directory |

Importing the library never creates files — only `c2epr-init` writes anything.

## Troubleshooting

**`ACTION REQUIRED: ... ip_address is still the placeholder`**
Step 2 has not been done. The address `192.0.2.50` is a deliberate
non-routable placeholder so an unconfigured install fails fast. A script that
passes `ip_address` does not need the config value set.

**`RuntimeError` about Windows or the Python version at import**
The client enforces Windows + CPython 3.11 or newer. Check with `python -V`.

**`no matching distribution found`**
Your Python is older than 3.11. The package declares `requires-python = ">=3.11"`.

**`test list rejected: ... not in the test catalog`**
A name is not in `test_case_list.json` at all. Names are checked before
anything is sent, so nothing ran. Re-run `c2epr-testcases` to refresh the
catalog for your VIF and copy the names verbatim. Whitespace-only differences
are not rejected: those are corrected for you and reported.

**App does not start**
Check `applications.C2-EPR.app_path` in `grlps_app_config.json`, and that the
C2-EPR software runs on its own.

**A test I selected never ran, or came back inconclusive**
Check the VIF. `c2epr-run` stops with a message if the VIF fails to load or
reports zero test cases, but a VIF that loads yet describes a *different* device
runs to completion and returns inconclusive results.

Logs for every run are written to `user_interaction\logs\`.

Reports are copied to `common.reportExportDir` - `user_interaction\reports_export\`
by default - one subfolder per run, so an earlier run's report is never replaced
by a later one. A relative path is resolved inside the workspace; set an
absolute path to collect reports elsewhere. A script can send a single run
somewhere else with `report_export_dir`, without touching the config.

## Documentation

| Guide | Covers |
|---|---|
| [User guide](grlps_api_client/docs/GRLPSApiClient_USER_GUIDE.md) | every method, full request/response examples |

The guide ships inside the package. Find it with:

```python
from grlps_api_client import docs_dir
print(docs_dir())
```

## License

Use of this software is governed by the GRL Platform Solutions Software End
User License Agreement — see [LICENSE](LICENSE).

This is **proprietary, source-available** software, not open source. The source
is published so you can read it, script against it and debug integrations. A
valid licence from GRL Platform Solutions is required to use it, and the EULA
does not permit redistribution, sublicensing, or reverse engineering.

GRLPS, GRL Platform Solutions and the GRL Platform Solutions logo are
trademarks of GRL Platform Solutions.
