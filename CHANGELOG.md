# Changelog

Notable changes to this package. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); version numbers track
the GRL C2-EPR release they were built against.

## 1.6.1.4 - 2026-09-19

Initial public release.

### Changed - BREAKING

- The console commands were renamed. Scripts and CI jobs calling the old names
  must be updated:

  | Before | Now |
  |---|---|
  | `grlps-api-client-init` | `c2epr-init` |
  | `grlps-get-testcases` | `c2epr-testcases` |
  | `grlps-sample-run` | `c2epr-run` |

- The distribution is now `usbpd-c2-epr-pyclient` (previously
  `grlps-api-client`). Uninstall the old name before installing this one:
  `pip uninstall grlps-api-client`.

The **import name is unchanged** - `from grlps_api_client import GRLPSApiClient`
keeps working, so Python code needs no edits.

### Fixed

- `c2epr-run` and `c2epr-testcases` exited with status 1 after a successful run,
  and printed their result dictionary to stderr. Both now return a proper exit
  code (`0` success, `1` failure).

### Changed

- Supported Python widened from 3.14 only to **3.11 or newer**. The package
  contains no version-specific syntax, so one pure-Python `py3-none-any` wheel
  covers 3.11, 3.12, 3.13 and 3.14 with no build toolchain required.
- The bundled example VIF is a generic `example_captive_cable.xml`.
