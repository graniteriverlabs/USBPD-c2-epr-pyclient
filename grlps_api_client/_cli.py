"""
Console entry points for the pip-installed client.

These wrap the shipped ``sample_run`` and ``get_testcases_only`` modules with a
check that the current directory has actually been initialised. The wrapped
modules are also used from a source checkout, where the workspace always exists,
so the check belongs here rather than in them.
"""
from __future__ import annotations

from ._bootstrap import require_workspace


def run() -> int:
    """``c2epr-run`` - the full start/connect/load/execute/report flow."""
    require_workspace()
    from .sample_run import cli

    return cli()


def testcases() -> int:
    """``c2epr-testcases`` - fetch the test catalog for the selected VIF."""
    require_workspace()
    from .get_testcases_only import cli

    return cli()
