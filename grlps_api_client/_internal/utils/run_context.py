"""
Per-run identity used to name log files.

One Python process is one run. The run id is computed once, on first use, so
every file produced by that run carries the same stamp and the files for a run
sort together in the log directory.
"""

import os
import time
from typing import Optional

RUN_ID_FORMAT = "%Y%m%d-%H%M%S"

_RUN_ID: Optional[str] = None


def get_run_id() -> str:
    """
    Stamp identifying this process run, e.g. '20260909-155501'.
    Stable for the lifetime of the process.
    """
    global _RUN_ID
    if _RUN_ID is None:
        _RUN_ID = time.strftime(RUN_ID_FORMAT)
    return _RUN_ID


def stamped_filename(filename: str, run_id: Optional[str] = None) -> str:
    """
    Insert the run id before the extension so each run writes its own file:
    'api_framework_session.log' becomes 'api_framework_session_20260909-155501.log'.
    A name without an extension gets the stamp appended.
    """
    rid = run_id or get_run_id()
    base, ext = os.path.splitext(filename or "")
    if not base:
        base = "log"
    return "{0}_{1}{2}".format(base, rid, ext)
