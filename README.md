# GRLPS C2-EPR API Client

Python client for the **GRL Platform Solutions (GRLPS) USB-PD C2-EPR** application. It drives the app over
its local HTTP API: start it, connect to the controller, load a VIF, pick test
cases, run them and collect the report — from a script or from the command line.

```python
from grlps_api_client import GRLPSApiClient

client = GRLPSApiClient()
client.start_app()
client.connect()
client.load_vif("my_device.xml")
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
pip install https://github.com/graniteriverlabs/USBPD-c2-epr-pyclient/releases/download/v1.6.1.4/usbpd_c2_epr_pyclient-1.6.1.4-py3-none-any.whl
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

```powershell
c2epr-init
```

This creates a folder you own and copies the default config into it:

```
C:\Users\<you>\AppData\Local\GRLPSApiClient\
```

The command prints the path and tells you what still needs setting. **Edit files
there, not in site-packages.** Your edits survive upgrades — the installer never
overwrites a file that already exists.

### 2. Set your controller address

Open `config\grlps_app_config.json` in that folder and replace the placeholder:

```json
"ip_address": "192.0.2.50"     →     "ip_address": "<your controller IP>"
```

Check `app_path` points at your GRLPS C2-EPR installation while you are there.

### 3. Add your VIF

Copy your VIF XML into the workspace and select it:

```powershell
copy C:\path\to\MyDevice.xml %LOCALAPPDATA%\GRLPSApiClient\user_interaction\vif\
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

> Names must match `test_case_list.json` **exactly**. Copy and paste them; a
> typo means the test is skipped silently.

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

```python
from grlps_api_client import GRLPSApiClient

client = GRLPSApiClient()

client.start_app()
connect = client.connect()
if not connect.get("connectionSetupSuccess"):
    raise SystemExit("controller not reachable")

client.create_project("MyProject")
client.load_vif("MyDevice.xml")

client.send_test_list([
    "TEST.PD.PHY.ALL.1 Transmit Bit Rate and the Drift",
])

result = client.run_testcases()
client.run_report_flow()
client.stop_app()
```

| Setting | Config file | In code |
|---|---|---|
| VIF | `common.selectedVifFile` | `client.load_vif("x.xml")` |
| Tests | `config/test_list_to_execute.json` | `client.send_test_list([...])` |
| Project name | `common.projectName` | `client.create_project("Name")` |

Every method returns a JSON-serialisable `dict`. See
[`examples/`](examples/) for complete scripts, and the
[programmer guide](grlps_api_client/docs/GRLPSApiClient_PROGRAMMER_GUIDE.md)
for the full method reference.

## The workspace

```
%LOCALAPPDATA%\GRLPSApiClient\
├── config\
│   ├── grlps_app_config.json       IP, VIF choice, timeouts, paths
│   ├── test_list_to_execute.json   which tests to run
│   ├── grlps_api_config.json       API endpoint map (leave alone)
│   ├── logging_config.json
│   └── put_port_config_mapping.json
└── user_interaction\
    ├── vif\                        put your VIF files here
    ├── test_cases_list\            generated: available tests
    └── logs\                       generated: session + app logs
```

Move it somewhere else if you prefer:

```powershell
set GRLPS_API_HOME=D:\benches\grl
c2epr-init
```

| Variable | Effect |
|---|---|
| `GRLPS_API_HOME` | where the per-user workspace is created |
| `GRLPS_API_PROJECT_ROOT` | use this directory as-is; nothing is copied into it |

## Troubleshooting

**`ACTION REQUIRED: ... ip_address is still the placeholder`**
Step 2 has not been done. The address `192.0.2.50` is a deliberate
non-routable placeholder so an unconfigured install fails fast.

**`RuntimeError` about Windows or the Python version at import**
The client enforces Windows + CPython 3.11 or newer. Check with `python -V`.

**`no matching distribution found`**
Your Python is older than 3.11. The package declares `requires-python = ">=3.11"`.

**A test name in `test_list_to_execute.json` never runs**
It does not match `test_case_list.json` exactly. Re-run `c2epr-testcases`
and copy the name verbatim.

**App does not start**
Check `applications.C2-EPR.app_path` in `grlps_app_config.json`, and that the
C2-EPR software runs on its own.

Logs for every run are written to `user_interaction\logs\`.

## Documentation

| Guide | Covers |
|---|---|
| [User guide](grlps_api_client/docs/GRLPSApiClient_USER_GUIDE.md) | every method, full request/response examples |
| [Programmer guide](grlps_api_client/docs/GRLPSApiClient_PROGRAMMER_GUIDE.md) | architecture and extension points |
| [Installer guide](grlps_api_client/docs/GRLPSApiClient_INSTALLER_END_USER_GUIDE.md) | the standalone `.exe` installer |

The same guides ship inside the package. Find them with:

```python
from grlps_api_client import docs_dir
print(docs_dir())
```

## Building from source

```powershell
pip install build
python -m build --wheel
pip install dist\usbpd_c2_epr_pyclient-1.6.1.4-py3-none-any.whl
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
