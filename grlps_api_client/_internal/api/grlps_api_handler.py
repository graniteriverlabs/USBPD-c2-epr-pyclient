"""
GRLPS API handler – call API by name (reference: GRLPS_PY_API_C3_ALL API/grlps_api_handler.py).
Uses base_url + path from config; GET/POST/PUT with optional data, params, files.
"""
import json
import os
import logging
from datetime import datetime
from http.client import responses as http_reasons
from typing import Dict, Any, Optional

import requests

from .result import Result, ApiResult
from .api_enum import ApiName
from utils.api_defaults import DEFAULT_API_CONFIG
from grlps_core.constants import DEFAULT_API_TIMEOUT_SECONDS


def _resolve_project_root_from_file(file_path: str) -> str:
    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


class GRLPSApiHandler:
    """Call C2-EPR (or GRLPS) API by ApiName. Loads method+path from config."""

    def __init__(
        self,
        base_url: str,
        config_path: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        create_get_test_results_json: bool = False,
        request_timeout: float = DEFAULT_API_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self._request_timeout = float(request_timeout)
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self.api_definitions = self._load_api_config(config_path)
        self._get_test_results_debug_seq = 0
        self._create_get_test_results_json = bool(create_get_test_results_json)
        self.logger.info("GRLPSApiHandler initialized: %s", self.base_url)

    def _load_api_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        if config_path and os.path.isfile(config_path):
            path = config_path
        else:
            path = os.path.join(_resolve_project_root_from_file(__file__), "config", "grlps_api_config.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.info(
                "API config file not found at %s; using built-in defaults (expected in customer build).",
                path,
            )
            return DEFAULT_API_CONFIG
        except json.JSONDecodeError as e:
            self.logger.warning("API config JSON invalid (%s). Using built-in defaults.", e)
            return DEFAULT_API_CONFIG

    def call_api(self, api_name: ApiName, **kwargs) -> ApiResult:
        """Execute API by name. kwargs: data=, params=, files=."""
        try:
            # GetMessageBox: log at DEBUG only to avoid poll spam when no message (msgbox monitor polls every 0.5s)
            if api_name in {ApiName.GET_MESSAGE_BOX, ApiName.GET_APP_STATE, ApiName.GET_TEST_RESULTS}:
                self.logger.debug("Executing: %s", api_name.value)
            else:
                self.logger.info("Executing: %s", api_name.value)
            config = self.api_definitions.get(api_name.value)
            if not config:
                return self._create_error_result("No config for: " + api_name.value, api_name, kwargs)
            method = config.get("method", "GET").upper()
            path = config.get("path", "").lstrip("/")
            # Optional path_suffix for any API (e.g. GetTestCaseList/APP, ConnectionSetup/0/192.0.2.50, PutVIFFile/filename.xml)
            if kwargs.get("path_suffix"):
                suffix = str(kwargs["path_suffix"]).strip().lstrip("/")
                if suffix:
                    path = path.rstrip("/") + "/" + suffix
            url = "{0}/{1}".format(self.base_url, path) if path else self.base_url
            files = kwargs.get("files")
            data = kwargs.get("data")
            params = kwargs.get("params")
            response = None
            # PutVIFFile: (1) filename only for report folder — PUT URL with filename, no body; (2) upload file — multipart VifFile (HAR)
            if api_name == ApiName.VIF_PATH and not files:
                path_suffix = kwargs.get("path_suffix") or (os.path.basename(kwargs["vif_file_path"]) if kwargs.get("vif_file_path") else None)
                if path_suffix:
                    if not path.strip("/").endswith(path_suffix):
                        path = path.rstrip("/") + "/" + path_suffix.lstrip("/")
                        url = "{0}/{1}".format(self.base_url, path) if path else self.base_url
                    if kwargs.get("vif_file_path"):
                        # Upload file: PUT multipart/form-data, field "VifFile", Content-Type text/xml (HAR)
                        vif_path = kwargs["vif_file_path"]
                        self.logger.debug("%s %s (VifFile)", method, url)
                        with open(vif_path, "rb") as f:
                            vif_files = {"VifFile": (os.path.basename(vif_path), f, "text/xml")}
                            response = self._make_request_with_files(method, url, params, None, vif_files)
                    else:
                        # Filename only: PUT with no body — server uses file from report folder (HAR URL only)
                        self.logger.debug("%s %s (filename only)", method, url)
                        response = self._make_request(method, url, params, None)
            if response is None:
                self.logger.debug("%s %s", method, url)
                if files:
                    response = self._make_request_with_files(method, url, params, data, files)
                else:
                    response = self._make_request(method, url, params, data)
            try:
                response_json = response.json() if response.content else {}
                content_type = "json"
            except Exception:
                response_json = response.text
                content_type = "text"
            result_value = self._build_api_result(
                api_name=api_name.value,
                method=method,
                url=url,
                params=params,
                data=data,
                status_code=response.status_code,
                response_data=response_json,
                content_type=content_type,
            )
            if api_name == ApiName.GET_TEST_RESULTS and self._create_get_test_results_json:
                self._save_get_test_results_debug(result_value)
            # Treat HTTP 4xx/5xx as failure (e.g. 404 file not found for VifPath filename-only)
            if response.status_code >= 400:
                err_msg = self._extract_error_message(response.status_code, response_json, content_type)
                # For VIF upload we intentionally do a "filename-only PUT" first.
                # That path can return 415; caller retries multipart and we don't want
                # this expected probe to look like a real error in logs.
                if api_name == ApiName.VIF_PATH and response.status_code == 415 and not kwargs.get("vif_file_path"):
                    self.logger.debug("%s: %s (expected 415; retrying multipart)", api_name.value, err_msg)
                else:
                    self.logger.warning("%s: %s", api_name.value, err_msg)
                return Result.failure(err_msg, metadata={"result_value": result_value})
            # HTTP 200 but JSON body may still report logical failure (e.g. ConnectionSetup success=false)
            body_err = self._logical_failure_from_body(api_name, response_json)
            if body_err:
                self.logger.warning("%s: %s", api_name.value, body_err)
                return Result.failure(body_err, metadata={"result_value": result_value})
            # VifPath (filename-only): treat 200 with error in body as failure (e.g. "file not found" from server)
            if api_name == ApiName.VIF_PATH and response.status_code == 200 and isinstance(response_json, dict):
                err_msg = self._vif_response_error(response_json)
                if err_msg:
                    self.logger.warning("VifPath: %s", err_msg)
                    return Result.failure(err_msg, metadata={"result_value": result_value})
            if api_name in {ApiName.GET_MESSAGE_BOX, ApiName.GET_APP_STATE, ApiName.GET_TEST_RESULTS}:
                self.logger.debug("Completed: %s", api_name.value)
            else:
                self.logger.info("Completed: %s", api_name.value)
            return Result.success(result_value)
        except Exception as e:
            self.logger.error("Error %s: %s", api_name.value, e)
            return self._create_error_result(str(e), api_name, kwargs)

    def _save_get_test_results_debug(self, result_value: Dict[str, Any]) -> None:
        """Append GetTestResults request/response snapshots into one JSON file."""
        try:
            self._get_test_results_debug_seq += 1
            project_root = _resolve_project_root_from_file(__file__)
            out_dir = os.path.join(project_root, "user_interaction", "logs")
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, "get_test_results_debug.json")
            record = {
                "savedAt": datetime.now().isoformat(timespec="milliseconds"),
                "apiCallIndex": self._get_test_results_debug_seq,
                "apiResult": result_value,
            }
            payload = {
                "generatedAt": datetime.now().isoformat(timespec="milliseconds"),
                "entries": [],
            }
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as rf:
                        existing = json.load(rf)
                    if isinstance(existing, dict):
                        payload["generatedAt"] = (
                            existing.get("generatedAt") or payload["generatedAt"]
                        )
                        entries = existing.get("entries")
                        if isinstance(entries, list):
                            payload["entries"] = entries
                except Exception:
                    # If existing file is malformed, replace with fresh payload.
                    pass
            payload["entries"].append(record)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self.logger.debug("GetTestResults debug snapshot: %s", path)
        except Exception as e:
            self.logger.debug("GetTestResults debug save failed: %s", e)

    def _make_request(self, method: str, url: str, params: Any, data: Any):
        t = self._request_timeout
        if method == "GET":
            return self.session.get(url, params=params, timeout=t)
        if method == "POST":
            return self.session.post(url, json=data, params=params, timeout=t)
        if method == "PUT":
            # PUT with no body must not send Content-Type: application/json (avoids 415 for VifPath filename-only)
            if data is None:
                return self.session.put(url, params=params, timeout=t)
            return self.session.put(url, json=data, params=params, timeout=t)
        raise ValueError("Unsupported method: %s", method)

    def _make_request_with_files(self, method: str, url: str, params: Any, data: Any, files: Any):
        if isinstance(files, dict):
            return self._send_multipart(method, url, params, data, files)
        if isinstance(files, str):
            with open(files, "rb") as f:
                return self._send_multipart(method, url, params, data, {"file": f})
        return self._send_multipart(method, url, params, data, {"file": files})

    def _send_multipart(self, method: str, url: str, params: Any, data: Any, files_dict: Dict):
        session = requests.Session()
        session.headers.update({"Accept": "application/json"})
        t = self._request_timeout
        if method == "POST":
            return session.post(url, data=data, files=files_dict, params=params, timeout=t)
        if method == "PUT":
            return session.put(url, data=data, files=files_dict, params=params, timeout=t)
        raise ValueError("Unsupported method for files: %s", method)

    def _build_api_result(
        self,
        api_name: str,
        method: str,
        url: str,
        params: Any,
        data: Any,
        status_code: int,
        response_data: Any,
        content_type: str,
    ) -> Dict[str, Any]:
        """
        Build the dict returned in Result.value for a successful API call.
        Change this method to change the return format (e.g. flatten, rename keys, or return only body).
        """
        return {
            "api_name": api_name,
            "request": {"method": method, "url": url, "params": params, "data": data},
            "response": {
                "status_code": status_code,
                "success": status_code == 200,
                "data": response_data,
                "content_type": content_type,
            },
        }

    def _logical_failure_from_body(self, api_name: ApiName, response_data: Any) -> Optional[str]:
        """
        Some endpoints return HTTP 200 with success=false in the JSON body.
        ConnectionSetup may also return 200 with testerStatus/Connected but boardCalibration
        or invalidFRAMVersion indicating the session is not usable for testing.
        """
        if not isinstance(response_data, dict):
            return None
        # Generic "success=false" handling (some endpoints use logical failure while HTTP is 200).
        # Keep ConnectionSetup-specific equipment checks below.
        if api_name != ApiName.CONNECTION_SETUP:
            ok = response_data.get("success")
            if ok is None:
                ok = response_data.get("Success")
            if ok is False:
                return (
                    response_data.get("error")
                    or response_data.get("Error")
                    or response_data.get("message")
                    or response_data.get("Message")
                    or response_data.get("ErrorMessage")
                    or response_data.get("errorMessage")
                    or "Request failed (success=false)"
                )
            return None
        ok = response_data.get("success")
        if ok is None:
            ok = response_data.get("Success")
        if ok is False:
            return (
                response_data.get("error")
                or response_data.get("Error")
                or response_data.get("message")
                or response_data.get("Message")
                or response_data.get("ErrorMessage")
                or response_data.get("errorMessage")
                or "Request failed (success=false)"
            )
        return self._connection_setup_data_issues(response_data)

    def _connection_setup_data_issues(self, d: Dict[str, Any]) -> Optional[str]:
        """Return a user-facing error string if C2-EPR body reports equipment issues, else None."""
        parts: list = []
        ts = d.get("testerStatus") or d.get("TesterStatus")
        if isinstance(ts, str) and ts.strip() and ts.strip().lower() != "connected":
            parts.append("testerStatus: %s" % ts.strip())
        if d.get("invalidFRAMVersion") is True:
            fw = d.get("framWarning") or d.get("FramWarning")
            if isinstance(fw, str) and fw.strip():
                parts.append(fw.strip())
            else:
                parts.append("invalidFRAMVersion is true")
        bc = d.get("boardCalibration") or d.get("BoardCalibration")
        if isinstance(bc, str) and bc.strip():
            bcl = bc.lower()
            if "error" in bcl or "calibration error" in bcl:
                parts.append("boardCalibration: %s" % bc.strip())
        if not parts:
            return None
        return "; ".join(parts)

    def _vif_response_error(self, data: Dict[str, Any]) -> Optional[str]:
        """If VifPath response body indicates error (e.g. file not found), return error message else None."""
        if data.get("success") is False:
            return data.get("error") or data.get("message") or "Request failed (success=false)"
        for key in ("error", "message", "ErrorMessage", "errorMessage", "detail"):
            val = data.get(key)
            if val and isinstance(val, str):
                val_lower = val.lower()
                if "not found" in val_lower or "file not found" in val_lower or "does not exist" in val_lower:
                    return val.strip()
        return None

    def _extract_error_message(self, status_code: int, response_data: Any, content_type: str) -> str:
        """Build a user-facing error string from HTTP status and response body (e.g. file not found)."""
        reason = http_reasons.get(status_code) or ("HTTP %d" % status_code)
        msg_parts = ["%d %s" % (status_code, reason)]
        if response_data is None:
            return msg_parts[0]
        if isinstance(response_data, dict):
            for key in ("error", "message", "detail", "ErrorMessage", "errorMessage"):
                val = response_data.get(key)
                if val and isinstance(val, str):
                    msg_parts.append(val.strip())
                    break
            if len(msg_parts) == 1 and response_data:
                msg_parts.append(json.dumps(response_data)[:200])
        elif isinstance(response_data, str) and response_data.strip():
            msg_parts.append(response_data.strip()[:200])
        return " - ".join(msg_parts)

    def _create_error_result(self, error_message: str, api_name: ApiName, kwargs: Dict) -> ApiResult:
        return Result.failure(error_message, metadata={"api_name": api_name.value, "kwargs": kwargs})
