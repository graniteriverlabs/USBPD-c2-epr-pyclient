"""
Small runtime helpers for Python 3.x customer builds (Windows-focused).
"""
import sys

# Python 3.x only — do not use this tree with Python 2.
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

input_compat = input


def raise_from(exc, cause=None):
    if cause is not None:
        raise exc from cause
    raise exc
