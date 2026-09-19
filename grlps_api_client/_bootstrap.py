"""
Workspace resolution for the pip-installed GRLPS API Client.

The shipped modules read configuration and VIF data from a project root, and
also *write* logs, test-case lists and reports beneath it. When the package is
installed with pip it lives in ``site-packages``, which is frequently read-only
or admin-owned, so runtime state cannot live there.

This module resolves a writable per-user workspace and seeds it once from the
read-only defaults bundled in the wheel.

Resolution order:

1. ``GRLPS_API_PROJECT_ROOT`` - used as-is; nothing is seeded. Set this to point
   at an existing checkout or a workspace you manage yourself.
2. ``GRLPS_API_HOME`` - overrides where the per-user workspace is created.
3. Default - ``LOCALAPPDATA/GRLPSApiClient`` on Windows, ``~/GRLPSApiClient``
   elsewhere.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

_PKG_DIR = Path(__file__).resolve().parent

# Read-only defaults copied out of the wheel on first use. Existing files in the
# workspace are never overwritten, so local edits survive an upgrade.
_SEED_DIRS = (
    "config",
    "user_interaction/vif",
    "user_interaction/test_cases_list",
)

# Created empty; runtime output only, never seeded.
_RUNTIME_DIRS = ("user_interaction/logs",)


def default_workspace() -> Path:
    """Return the per-user workspace location (not necessarily created yet)."""
    override = os.environ.get("GRLPS_API_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base).joinpath("GRLPSApiClient").resolve()


def _seed_dir(rel: str, workspace: Path) -> List[str]:
    """Copy bundled defaults for one relative directory. Returns copied names."""
    parts = rel.split("/")
    src = _PKG_DIR.joinpath(*parts)
    if not src.is_dir():
        return []
    dst = workspace.joinpath(*parts)
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for item in src.iterdir():
        if not item.is_file():
            continue
        target = dst / item.name
        if not target.exists():
            shutil.copy2(item, target)
            copied.append("{0}/{1}".format(rel, item.name))
    return copied


def ensure_workspace() -> Path:
    """
    Return the project root to use, seeding a per-user workspace when needed.

    Honours ``GRLPS_API_PROJECT_ROOT`` verbatim when it is already set.
    """
    existing = os.environ.get("GRLPS_API_PROJECT_ROOT", "").strip()
    if existing:
        return Path(existing).expanduser().resolve()

    workspace = default_workspace()
    workspace.mkdir(parents=True, exist_ok=True)
    for rel in _SEED_DIRS:
        _seed_dir(rel, workspace)
    for rel in _RUNTIME_DIRS:
        workspace.joinpath(*rel.split("/")).mkdir(parents=True, exist_ok=True)
    return workspace


# Shipped as a deliberate placeholder (RFC 5737 TEST-NET-1, non-routable) so an
# unconfigured install fails fast instead of reaching some arbitrary host.
PLACEHOLDER_IP = "192.0.2.50"


def unconfigured_warnings(workspace: Path) -> List[str]:
    """Flag settings the site must supply before the client can connect."""
    import json

    config = workspace / "config" / "grlps_app_config.json"
    if not config.is_file():
        return ["WARNING: {0} is missing.".format(config)]

    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["WARNING: could not read {0}: {1}".format(config, exc)]

    warnings = []
    for app_name, app in (data.get("applications") or {}).items():
        if isinstance(app, dict) and app.get("ip_address") == PLACEHOLDER_IP:
            warnings.append(
                "ACTION REQUIRED: applications.{0}.ip_address is still the\n"
                "  placeholder {1}. Set your controller address in:\n"
                "    {2}".format(app_name, PLACEHOLDER_IP, config)
            )
    return warnings


def docs_dir() -> Path:
    """Location of the bundled customer guides (read-only, inside the package)."""
    return _PKG_DIR / "docs"


def describe_workspace() -> str:
    """Human-readable summary of the resolved workspace and its contents."""
    workspace = ensure_workspace()
    lines = ["GRLPS API Client workspace: {0}".format(workspace)]
    for rel in _SEED_DIRS + _RUNTIME_DIRS:
        path = workspace.joinpath(*rel.split("/"))
        count = len(list(path.glob("*"))) if path.is_dir() else 0
        status = "ok" if path.is_dir() else "MISSING"
        lines.append("  {0:<34} {1:>4} file(s)  [{2}]".format(rel, count, status))

    for warning in unconfigured_warnings(workspace):
        lines.append("")
        lines.append(warning)

    docs = docs_dir()
    if docs.is_dir():
        lines.append("")
        lines.append("Bundled documentation: {0}".format(docs))
        for item in sorted(docs.glob("*.md")):
            lines.append("  {0}".format(item.name))
    lines.append("")
    lines.append("Point the client at this workspace with:")
    lines.append('  set GRLPS_API_PROJECT_ROOT={0}'.format(workspace))
    return "\n".join(lines)


def main() -> int:
    """Console entry point: seed the workspace and report what it contains."""
    print(describe_workspace())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
