"""
Workspace resolution for the pip-installed GRLPS API Client.

The shipped modules read configuration and VIF data from a project root, and
also *write* logs, test-case lists and reports beneath it. When the package is
installed with pip it lives in ``site-packages``, which is frequently read-only
or admin-owned, so runtime state cannot live there.

This module resolves a writable workspace and seeds it from the read-only
defaults bundled in the wheel.

The workspace is **the directory you run in**, so your config, VIF files and
logs sit where you are working rather than in a hidden per-user folder. Each
test bench or project directory gets its own independent setup.

Resolution order:

1. ``GRLPS_API_PROJECT_ROOT`` - used as-is. Set this to point at an existing
   checkout or a workspace you manage yourself.
2. ``GRLPS_API_HOME`` - an explicit workspace location, used instead of the
   current directory.
3. Default - the current working directory.

Only ``c2epr-init`` writes anything. Importing the package resolves the
workspace but never creates or seeds files, so ``import grlps_api_client`` in an
arbitrary directory leaves it untouched.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

_PKG_DIR = Path(__file__).resolve().parent

# Read-only defaults copied out of the wheel by ``c2epr-init``. Existing files in
# the workspace are never overwritten, so local edits survive an upgrade.
_SEED_DIRS = (
    "config",
    "user_interaction/vif",
)

# Created empty; runtime output only, never seeded. The test-case catalog belongs
# here rather than in _SEED_DIRS: it depends entirely on the VIF in use, so a
# shipped copy would list tests the local device does not support.
# ``c2epr-testcases`` writes the correct one on first run.
_RUNTIME_DIRS = (
    "user_interaction/logs",
    "user_interaction/test_cases_list",
)


def default_workspace() -> Path:
    """Where a workspace is created: ``GRLPS_API_HOME``, else the current directory."""
    override = os.environ.get("GRLPS_API_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd().resolve()


def resolve_workspace() -> Path:
    """
    The project root to read from. Creates nothing and seeds nothing.

    Used at import time, where writing files would be an unwanted side effect of
    ``import grlps_api_client``.
    """
    existing = os.environ.get("GRLPS_API_PROJECT_ROOT", "").strip()
    if existing:
        return Path(existing).expanduser().resolve()
    return default_workspace()


def is_initialised(workspace: Path) -> bool:
    """True once ``c2epr-init`` has seeded this directory."""
    return (workspace / "config" / "grlps_app_config.json").is_file()


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
    Create and seed the workspace, then return it. This is what ``c2epr-init`` runs.

    Existing files are never overwritten, so running it again in a configured
    directory is safe and only restores anything missing.
    """
    workspace = resolve_workspace()
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


def require_workspace() -> Path:
    """
    Stop with a clear instruction when the current directory is not set up.

    Without this the first missing config surfaces as a ``FileNotFoundError``
    traceback from deep inside the config manager, which tells a new user
    nothing useful.
    """
    workspace = resolve_workspace()
    if not is_initialised(workspace):
        raise SystemExit(
            "No GRLPS C2-EPR workspace in:\n"
            "  {0}\n\n"
            "Run 'c2epr-init' in this directory first, or point\n"
            "GRLPS_API_PROJECT_ROOT at a directory you have already "
            "initialised.".format(workspace)
        )
    return workspace


def docs_dir() -> Path:
    """Location of the bundled customer guides (read-only, inside the package)."""
    return _PKG_DIR / "docs"


def describe_workspace() -> str:
    """Human-readable summary of the resolved workspace and its contents."""
    workspace = resolve_workspace()
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
    lines.append("Run c2epr-testcases and c2epr-run from this directory.")
    lines.append("To use it from elsewhere:")
    lines.append("  set GRLPS_API_PROJECT_ROOT={0}".format(workspace))
    return "\n".join(lines)


def main() -> int:
    """Console entry point: seed the workspace here and report what it contains."""
    ensure_workspace()
    print(describe_workspace())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
