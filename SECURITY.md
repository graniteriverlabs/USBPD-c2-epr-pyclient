# Security Policy

## Reporting a vulnerability

Please report security issues privately to **security@grlps.com** rather than
opening a public issue.

Include the version (`python -c "import grlps_api_client; print(grlps_api_client.__version__)"`),
what you observed, and how to reproduce it. We aim to acknowledge within five
working days.

## Scope

This package is a client that talks to the GRL C2-EPR application over a local
HTTP API. Issues in the C2-EPR application itself should also go to the address
above, noting the application version.

Do not include customer names, VIF files or captured traffic from a device you
do not own in a report.
