"""
Test cases framework: fetch from controller and save to two JSON files (like GRLPS_PY_API_C3_ALL).
- test_case_list_raw.json: same received data from GetTestCaseList API.
- test_case_list.json: list of test case names only.
"""
from __future__ import print_function

import os

from .test_cases_fetcher import fetch_test_cases
from .test_cases_storage import (
    save_raw_to_file,
    save_list_to_file,
    DEFAULT_FILENAME,
    DEFAULT_RAW_FILENAME,
)


def _resolve_project_root_from_file(file_path):
    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


def _repo_root():
    """Project root (parent of test_cases package) so output dir is same regardless of cwd."""
    return _resolve_project_root_from_file(__file__)


def _resolve_output_dir(output_dir):
    """If output_dir is relative, resolve against repo root so user_interaction is always in project."""
    if not output_dir:
        return output_dir
    if os.path.isabs(output_dir):
        return output_dir
    return os.path.join(_repo_root(), output_dir)


def _get_test_cases_options_from_config(config_manager):
    """Read from config: common.testCasesDir, testCasesJsonName, testCasesRawJsonName, getTestCaseListSuffix."""
    log_dir = None
    log_filename = None
    raw_filename = None
    path_suffix = None
    if config_manager is not None:
        try:
            common = config_manager.get_common()
            if isinstance(common, dict):
                log_dir = common.get("testCasesDir")
                log_filename = common.get("testCasesJsonName")
                raw_filename = common.get("testCasesRawJsonName")
                path_suffix = common.get("getTestCaseListSuffix")
        except Exception:
            pass
    return {"log_dir": log_dir, "log_filename": log_filename, "raw_filename": raw_filename, "path_suffix": path_suffix}


class TestCasesFramework(object):
    """
    Fetch test cases from controller (GetTestCaseList) and save to two files in the same folder:
    - Raw file: same data as received from API (test_case_list_raw.json).
    - List file: array of test case names only (test_case_list.json).
    """

    def __init__(self, logger=None, output_dir=None, output_filename=None, raw_filename=None, config_manager=None):
        """
        :param logger: Optional logger.
        :param output_dir: Directory for both JSON files. Overridden by config if config_manager given.
        :param output_filename: List file name (test_case_list.json). Overridden by config.
        :param raw_filename: Raw file name (test_case_list_raw.json). Overridden by config.
        :param config_manager: If set, reads common.testCasesDir, testCasesJsonName, testCasesRawJsonName.
        """
        self.logger = logger
        opts = {"log_dir": output_dir, "log_filename": output_filename, "raw_filename": raw_filename}
        self._path_suffix = None  # optional GetTestCaseList URL suffix, e.g. APP, BPP
        if config_manager is not None:
            from_config = _get_test_cases_options_from_config(config_manager)
            if from_config.get("log_dir") is not None:
                opts["log_dir"] = _resolve_output_dir(from_config["log_dir"])
            if from_config.get("log_filename") is not None:
                opts["log_filename"] = from_config["log_filename"]
            if from_config.get("raw_filename") is not None:
                opts["raw_filename"] = from_config["raw_filename"]
            if from_config.get("path_suffix") is not None:
                self._path_suffix = from_config["path_suffix"]
        elif opts.get("log_dir"):
            opts["log_dir"] = _resolve_output_dir(opts["log_dir"])

        self._output_dir = opts.get("log_dir") or os.getcwd()
        self._output_filename = opts.get("log_filename") or DEFAULT_FILENAME
        self._raw_filename = opts.get("raw_filename") or DEFAULT_RAW_FILENAME
        self._file_path = os.path.join(self._output_dir, self._output_filename)
        self._raw_file_path = os.path.join(self._output_dir, self._raw_filename)

    def get_file_path(self):
        """Return the path of the list file (test_case_list.json)."""
        return self._file_path

    def get_raw_file_path(self):
        """Return the path of the raw file (test_case_list_raw.json)."""
        return self._raw_file_path

    def fetch_and_save(self, handler, path_suffix=None):
        """
        Call GetTestCaseList, extract names, save to two files (raw + list only).
        path_suffix: optional URL suffix (e.g. APP, BPP) if C2 requires it for full list; else from config getTestCaseListSuffix.
        :return: (raw_data, test_case_names) or (None, None) on failure.
        """
        suffix = path_suffix if path_suffix is not None else getattr(self, "_path_suffix", None)
        raw_data, names = fetch_test_cases(handler, path_suffix=suffix, logger=self.logger)
        if raw_data is None and (names is None or names == []):
            if self.logger:
                self.logger.warning("[test_cases] No data from GetTestCaseList")
            return None, None

        ok_raw = save_raw_to_file(self._raw_file_path, raw_data, logger=self.logger)
        ok_list = save_list_to_file(self._file_path, names or [], logger=self.logger)
        if self.logger and (not ok_raw or not ok_list):
            self.logger.error("[test_cases] Failed to write raw=%s list=%s", ok_raw, ok_list)
        return raw_data, (names or [])

