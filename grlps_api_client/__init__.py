"""
GRLPS API Client - installable distribution.

The public API::

    from grlps_api_client import GRLPSApiClient

Runtime requirement: Windows + CPython 3.11 or newer. The facade enforces this at
import time and raises ``RuntimeError`` on anything else.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

__version__ = "1.6.1.2"

_PKG_DIR = Path(__file__).resolve().parent
_INTERNAL_DIR = _PKG_DIR / "_internal"

# The shipped modules import one another by their original top-level names
# (``from api import ApiName``, ``from utils.run_context import ...``). Those
# names are far too generic to install at the top level of site-packages, so the
# tree is bundled under ``_internal`` and that directory is put on sys.path here.
# This keeps every original import working without editing the shipped sources.
if _INTERNAL_DIR.is_dir():
    _internal_path = str(_INTERNAL_DIR)
    if _internal_path not in sys.path:
        sys.path.insert(0, _internal_path)

from ._bootstrap import (  # noqa: E402
    default_workspace,
    describe_workspace,
    docs_dir,
    ensure_workspace,
    is_initialised,
    resolve_workspace,
)

# Must happen before the facade is imported. The facade defaults the project root
# to its own directory, which under pip is site-packages - not writable, and not
# where the customer's config belongs.
#
# This resolves only; it never creates or seeds files. Importing the package must
# not write into whatever directory the caller happens to be in - seeding is the
# job of ``c2epr-init``.
os.environ.setdefault("GRLPS_API_PROJECT_ROOT", str(resolve_workspace()))

from ._facade import GRLPSApiClient  # noqa: E402

__all__ = [
    "GRLPSApiClient",
    "default_workspace",
    "describe_workspace",
    "docs_dir",
    "ensure_workspace",
    "is_initialised",
    "resolve_workspace",
    "__version__",
]
