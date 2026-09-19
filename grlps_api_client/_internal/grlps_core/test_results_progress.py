"""
Pure helpers for GetTestResults polling: labels, progress extraction, and log fragments.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def short_label_expected_test(full_name: str) -> str:
    """Short label for progress (keeps SRC.n + readable tail)."""
    parts = full_name.split(" ", 1)
    if len(parts) == 2:
        prefix, rest = parts
        m = re.search(r"SRC\.(\d+)", prefix)
        if m:
            return f"SRC.{m.group(1)} {rest}"
        return rest
    return full_name


def truncate_progress_field(text: Any, max_len: int) -> str:
    if text is None:
        return "-"
    t = str(text).replace("\n", " ").strip()
    if not t:
        return "-"
    if len(t) <= max_len:
        return t
    return t[: max_len - 3] + "..."


def pick_current_test_from_ordered_states(
    expected_names: List[str],
    states_map: Dict[str, str],
) -> Optional[str]:
    """
    Active test = first in plan order whose controller result is not finished.
    Finished = PASS, FAIL, NA, INCOMPLETE (matches typical GetTestResults usage).
    """
    done = {"PASS", "FAIL", "NA", "INCOMPLETE"}
    for name in expected_names:
        st = str(states_map.get(name, "NOT_EXECUTED")).upper()
        if st not in done:
            return name
    return expected_names[-1] if expected_names else None


def run_testcases_progress_detail(
    prog: Dict[str, Any],
    states_map: Dict[str, str],
    expected_total: int,
    full_states_max: int,
    expected_names: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    Build one progress fragment: either per-test `states=...` (small plans) or
    aggregate `stats=...` (large plans). Returns (fragment, mode) with mode full|compact.
    """
    if expected_total > 0 and expected_total <= full_states_max:
        if states_map or expected_names:
            keys = expected_names if expected_names else list(states_map.keys())
            parts = []
            for k in keys:
                parts.append(
                    f"{short_label_expected_test(k)}:{states_map.get(k, 'NOT_EXECUTED')}"
                )
            states_str = ",".join(parts) if parts else "-"
            return f"states={states_str}", "full"
        return "states=-", "full"
    total = int(prog.get("total") or 0)
    completed = int(prog.get("completed") or 0)
    pending = max(0, total - completed)
    frag = (
        f"stats=pass={prog['passCount']} fail={prog['failCount']} "
        f"incomplete={prog['incompleteCount']} other={prog['otherCount']} pending={pending}"
    )
    return frag, "compact"


def extract_expected_test_states(
    test_results_body: Dict[str, Any],
    expected_test_names: List[str],
) -> Dict[str, str]:
    """
    Snapshot of each expected test's controller-reported `result`.
    Post-order walk so deeper nodes override parents for the same displayString.
    """
    if not isinstance(test_results_body, dict):
        return {}
    expected_set = set(expected_test_names)
    states: Dict[str, str] = {}

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        for c in node.get("children") or []:
            walk(c)
        disp = node.get("displayString")
        if isinstance(disp, str) and disp in expected_set:
            key_str = disp
            res = node.get("result")
            res_str = str(res).upper() if res is not None else "?"
            states[key_str] = res_str

    top_nodes = test_results_body.get("testResults")
    if isinstance(top_nodes, list):
        for n in top_nodes:
            walk(n)
    return states


def extract_test_progress(
    test_results_body: Dict[str, Any],
    total_expected: int,
    expected_test_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Extract completed/total/currentTest and pass/fail/incomplete/other from GetTestResults body."""
    summary = test_results_body.get("summary") if isinstance(test_results_body, dict) else {}
    if not isinstance(summary, dict):
        summary = {}

    def _as_int(v: Any) -> int:
        try:
            return int(v)
        except Exception:
            return 0

    pass_count = _as_int(summary.get("passCount"))
    fail_count = _as_int(summary.get("failCount"))
    incomplete_count = _as_int(summary.get("incompleteCount"))
    other_count = _as_int(summary.get("otherCount"))

    total = summary.get("totalTestCaseCount")
    total_val = _as_int(total) if total is not None else total_expected
    if total_val == 0 and total_expected > 0:
        total_val = total_expected
    completed_val = pass_count + fail_count + incomplete_count

    terminal_results = {"PASS", "FAIL", "NA", "NOT_EXECUTED", "INCOMPLETE"}

    top_nodes = []
    if isinstance(test_results_body, dict):
        top_nodes = test_results_body.get("testResults") or []
    current_test = None
    states_map: Dict[str, str] = {}

    if expected_test_names:
        states_map = extract_expected_test_states(
            test_results_body if isinstance(test_results_body, dict) else {},
            list(expected_test_names),
        )
        current_test = pick_current_test_from_ordered_states(
            list(expected_test_names),
            states_map,
        )

    if not current_test:
        def walk_nodes(nodes):
            for n in nodes or []:
                if not isinstance(n, dict):
                    continue
                children = n.get("children") or []
                if children:
                    yield from walk_nodes(children)
                else:
                    yield n

        leaves = list(walk_nodes(top_nodes))
        for leaf in leaves:
            res = str(leaf.get("result") or "").upper()
            if res and res not in terminal_results:
                current_test = leaf.get("displayString") or leaf.get("id")
                break
        if not current_test and leaves:
            current_test = leaves[0].get("displayString") or leaves[0].get("id")

    percent = (completed_val / total_val * 100.0) if total_val > 0 else 0.0
    return {
        "passCount": pass_count,
        "failCount": fail_count,
        "incompleteCount": incomplete_count,
        "otherCount": other_count,
        "completed": completed_val,
        "total": total_val,
        "percent": percent,
        "currentTest": current_test,
        "statesMap": states_map,
    }
