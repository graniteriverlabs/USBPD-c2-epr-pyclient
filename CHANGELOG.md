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
- `c2epr-init` sets a project folder up in the directory you run it in, keeping
  your config, VIF files and logs together. One folder drives as many devices as
  you like. Nothing is written anywhere else, and re-running it only restores
  missing files, so your settings survive an upgrade.
- Reports are exported one subfolder per run, so a later run cannot replace an
  earlier run's report.
- `c2epr-run` stops with a clear message when the VIF fails to load or reports
  zero test cases, instead of running the suite against whatever VIF the
  application already had loaded.
- The user guide and installer guide ship inside the package; locate them with
  `docs_dir()`.
- A generic `example_captive_cable.xml` VIF, so the full flow runs before you
  supply your own.

### Fixed

- Cable selection is now chosen from the device type as well as the VIF's
  `Captive_Cable` flag. A cable DUT is the only cable in the test path, so it is
  sent as `No Cable ( For Cable Testing )`; previously a GRL test cable was
  reported that is not physically present, and cable runs came back incomplete.
- PortB, the tester's own port, always reports `GRL-SPL EPR Test Cable 1`.
  Previously it mirrored PortA, so a captive-cable device sent the wrong cable
  selection on PortB.
- `config/put_port_config_mapping.json` is now read at run time. It described
  the port and cable mapping but nothing loaded it, so editing it had no effect.
  Edits to it now take effect, and the selected device type and cable are
  printed when the VIF loads.

### Notes

- If your project folder was created by an earlier build, its
  `config/put_port_config_mapping.json` is kept as-is, because `c2epr-init`
  never overwrites your files. The client says so at run time. Delete that file
  and run `c2epr-init` to pick up the corrected table, unless you have edited it
  yourself.
- Runs on Windows with CPython 3.11 or newer. A single pure-Python
  `py3-none-any` wheel covers 3.11, 3.12, 3.13 and 3.14 - no build toolchain
  and no per-version wheels.
- Install from a GitHub Release asset or with `pip install git+https://...`.
  This package is not published to PyPI.
- Importing the package never creates files. Only `c2epr-init` writes anything,
  so `import grlps_api_client` from any directory leaves it untouched.
