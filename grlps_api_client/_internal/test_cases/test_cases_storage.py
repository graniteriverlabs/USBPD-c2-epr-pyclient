"""
Test cases storage: save raw API response and list of names to separate JSON files.
Like GRLPS_PY_API_C3_ALL: Test_cases_list (raw received data), Received_test_cases (list of names only).
"""
from __future__ import print_function

import errno
import json
import os

try:
    from typing import Any, List, Optional
except ImportError:
    pass


# File names: raw = same as received from API; list = test case names only
DEFAULT_FILENAME = "test_case_list.json"
DEFAULT_RAW_FILENAME = "test_case_list_raw.json"


def _ensure_dir(dir_path, logger=None):
    if not dir_path:
        return True
    if os.path.isdir(dir_path):
        return True
    try:
        os.makedirs(dir_path)
        return True
    except OSError as e:
        if getattr(e, "errno", None) != errno.EEXIST:
            if logger:
                logger.warning("[test_cases] Could not create dir %s: %s", dir_path, e)
            return False
    return True


def save_raw_to_file(file_path, raw_data, logger=None):
    """
    Write raw API response to a JSON file (same structure as received).
    Like GRLPS_PY_API_C3_ALL TEST_CASES_LIST / Test_cases_list.json.
    :param file_path: Full path (e.g. test_cases/test_case_list_raw.json).
    :param raw_data: Raw response (list or dict) to store as-is.
    :param logger: Optional logger.
    :return: True if written, False on error.
    """
    try:
        dir_path = os.path.dirname(file_path)
        if not _ensure_dir(dir_path, logger):
            return False
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        if logger:
            logger.info("[test_cases] Saved raw to %s", file_path)
        return True
    except Exception as e:
        if logger:
            logger.error("[test_cases] Failed to save raw: %s", e)
        return False


def save_list_to_file(file_path, test_case_names, logger=None):
    """
    Write list of test case names only to a JSON file (array of strings).
    Like GRLPS_PY_API_C3_ALL RECEIVED_TEST_CASES / Received_test_cases.json.
    :param file_path: Full path (e.g. test_cases/test_case_list.json).
    :param test_case_names: List of strings.
    :param logger: Optional logger.
    :return: True if written, False on error.
    """
    try:
        dir_path = os.path.dirname(file_path)
        if not _ensure_dir(dir_path, logger):
            return False
        names = test_case_names if test_case_names is not None else []
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(names, f, indent=2, ensure_ascii=False)
        if logger:
            logger.info("[test_cases] Saved list to %s (names: %s)", file_path, len(names))
        return True
    except Exception as e:
        if logger:
            logger.error("[test_cases] Failed to save list: %s", e)
        return False


def save_test_cases_to_file(
    file_path,
    raw_data=None,
    test_case_names=None,
    logger=None,
):
    """
    Deprecated: use save_raw_to_file and save_list_to_file separately.
    Kept for backward compatibility; writes combined structure to file_path.
    """
    try:
        dir_path = os.path.dirname(file_path)
        if not _ensure_dir(dir_path, logger):
            return False
        out = {}
        if raw_data is not None:
            out["raw"] = raw_data
        if test_case_names is not None:
            out["testCaseNames"] = test_case_names
        if not out:
            out = {"raw": None, "testCaseNames": []}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        if logger:
            logger.info("[test_cases] Saved to %s (names: %s)", file_path, len(test_case_names or []))
        return True
    except Exception as e:
        if logger:
            logger.error("[test_cases] Failed to save: %s", e)
        return False

