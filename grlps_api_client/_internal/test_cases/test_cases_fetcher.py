"""
Test cases fetcher: call GetTestCaseList API and optionally extract test case names.
Reference: GRLPS_PY_API_C3_ALL collection_operations._get_test_cases_from_api, _extract_test_cases.
"""
from __future__ import print_function

try:
    from typing import Any, Dict, List, Optional, Tuple
except ImportError:
    pass


def fetch_test_cases(handler, path_suffix=None, logger=None):
    """
    Call GetTestCaseList via handler. Return (raw_data, extracted_names) or (None, None) on failure.
    C2-EPR returns a list of nodes (e.g. Coil) each with "key" and "children" (see test2.py / AllMOIRun).
    :param handler: GRLPSApiHandler (or object with call_api(api_name, **kwargs) returning ApiResult).
    :param path_suffix: Optional; reserved for future URL suffix. Not used by default handler.
    :param logger: Optional logger for debug (e.g. when no data or 0 names).
    :return: (raw_data, list_of_test_case_names) or (None, None). raw_data is the full API body (list); names from tree.
    """
    if not handler:
        return None, None
    try:
        from api import ApiName

        kwargs = {}
        if path_suffix:
            kwargs["path_suffix"] = path_suffix

        result = handler.call_api(ApiName.GET_TEST_CASE_LIST, **kwargs)
        if not result.is_success or not result.value:
            if logger:
                logger.debug(
                    "[test_cases] GetTestCaseList failed or no value: success=%s",
                    getattr(result, "is_success", None),
                )
            return None, None

        response = result.value.get("response") or {}
        # success: status_code 200; data: raw HTTP body (C2 returns list of Coil nodes)
        if not response.get("success"):
            if logger:
                logger.debug("[test_cases] GetTestCaseList response success=False")
            return None, None

        data = response.get("data")
        if data is None:
            if logger:
                logger.debug("[test_cases] GetTestCaseList response.data is None")
            return None, None

        # Unwrap: server may send list directly or { "data"/"result"/"items": [ ... ] }
        if isinstance(data, dict):
            for key in ("data", "result", "items", "testCases"):
                if key in data and isinstance(data[key], (list, dict)):
                    data = data[key]
                    break

        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict):
            raw = data
        else:
            raw = None

        if raw is None:
            return None, None

        names = _extract_test_case_names(raw)
        if logger and not names and (isinstance(raw, list) and len(raw) > 0):
            logger.info(
                "[test_cases] GetTestCaseList returned %s top-level node(s) but extracted 0 names. "
                "If nodes have empty key/title, load a project in the C2 app first.",
                len(raw),
            )

        return raw, names
    except Exception as e:
        if logger:
            logger.debug("[test_cases] fetch_test_cases error: %s", e)
        return None, None


def _node_display_name(node):
    """Preferred name for a node: key, else title, else displayString. Skip empty."""
    for k in ("key", "title", "displayString"):
        v = node.get(k)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _extract_test_case_names(data):
    """
    Extract test case name strings from tree structure (key + children).
    C2-EPR: Coil -> children -> MOI -> children -> TC; leaf = node with no children (or empty list).
    Name from key, or title, or displayString (C2 may return key="" and use title/displayString).
    Treat missing or None "children" as empty. Skip nodes with no usable name (e.g. placeholder root).
    """
    names = []

    def find_names(node):
        if isinstance(node, dict):
            children = node.get("children")
            if children is None:
                children = []
            if len(children) == 0:
                name = _node_display_name(node)
                if name:
                    names.append(name)
            for child in children:
                find_names(child)
        elif isinstance(node, list):
            for item in node:
                find_names(item)

    find_names(data)
    return names

