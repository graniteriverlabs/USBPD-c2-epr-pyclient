# Changelog

Notable changes to this package. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); version numbers track
the GRLPS C2-EPR release they were built against.

## 1.6.1.2 - 2026-09-21

Initial public release of the GRL Platform Solutions C2-EPR Python client.

### Added

- Console commands `c2epr-init`, `c2epr-testcases` and `c2epr-run`. Each returns
  exit code `0` on success and `1` on failure, so they drop straight into CI.
- Library use: `from grlps_api_client import GRLPSApiClient`.
- `c2epr-init` sets a project folder up in the directory you run it in, so each
  bench or device keeps its own config, VIF files and logs side by side. Nothing
  is written anywhere else, and re-running it only restores missing files, so
  your settings survive an upgrade.
- The user guide and installer guide ship inside the package; locate them with
  `docs_dir()`.
- A generic `example_captive_cable.xml` VIF, so the full flow runs before you
  supply your own.

### Notes

- Runs on Windows with CPython 3.11 or newer. A single pure-Python
  `py3-none-any` wheel covers 3.11, 3.12, 3.13 and 3.14 - no build toolchain
  and no per-version wheels.
- Install from a GitHub Release asset or with `pip install git+https://...`.
  This package is not published to PyPI.
- Importing the package never creates files. Only `c2epr-init` writes anything,
  so `import grlps_api_client` from any directory leaves it untouched.
