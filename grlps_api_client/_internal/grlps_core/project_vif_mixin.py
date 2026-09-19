"""Stage-2 project folder + VIF load (PutProjectFolder, PutVIFFile, PutVIFData, PutPortConfigurations)."""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

from api import ApiName
from api.result import api_result_to_json_dict


class ProjectVifMixin:
    """Mixin: `create_project` and `load_vif` (requires `call_api`, `logger`, `_config_manager`, `_get_common`)."""

    def create_project(self, project_name: Optional[str] = None) -> dict:
        """
        Stage 2 - create project folder on controller.

        HAR shows PUT /api/App/PutProjectFolderName/<projectName> with body {}.
        """
        common = self._get_common()
        resolved_project_name = (project_name or common.get("projectName") or "").strip()
        if not resolved_project_name:
            return {
                "success": False,
                "projectName": None,
                "message": "Missing project folder name (set common.projectName in config).",
            }

        put_res = self.call_api(ApiName.PUT_PROJECT_FOLDER, path_suffix=resolved_project_name, data={})
        payload = {
            "success": bool(put_res.is_success),
            "projectName": resolved_project_name,
            "putProjectFolder": api_result_to_json_dict(put_res),
        }
        if put_res.is_success:
            print(f"  Project: {resolved_project_name} created (PutProjectFolder)", file=sys.stderr, flush=True)
        return payload

    def _find_vif_decoded_port_field(self, vif_data: Dict[str, Any], enum_name: str) -> Optional[str]:
        """Extract decodedValue of a port field from converted VIF JSON."""
        for comp in vif_data.get("vifComponents", []) if isinstance(vif_data, dict) else []:
            for f in comp.get("staticPortElements", []):
                if not isinstance(f, dict):
                    continue
                if f.get("enum") == enum_name:
                    dv = f.get("decodedValue")
                    if dv is None:
                        dv = f.get("specValue")
                    if dv is not None:
                        return str(dv)
        return None

    def _build_port_config_from_vif(self, vif_data: Dict[str, Any], vif_file_name: str) -> Dict[str, Any]:
        """
        Build PutPortConfigurations payload.

        Keep mapping aligned with HAR behavior while remaining data-driven:
        - vifFileName is the loaded VIF basename (same as PutVIFFile), matching primary HAR traffic
        - PortA dutType is inferred from Product_Type / PD_Port_Type
        - PortB dutType is Provider Only (HAR-observed constant)
        - stateMachineType is SRC for both ports (HAR-observed constant)
        - cableType is derived from Captive_Cable flag in VIF:
          true -> Captive Cable, false -> GRL-SPL EPR Test Cable 1
        - executionMode and rerenderRandomNum remain HAR-observed constants for now
        """
        pd_port_type = self._find_vif_decoded_port_field(vif_data, "PD_Port_Type") or ""
        product_type = self._find_vif_decoded_port_field(vif_data, "Product_Type") or ""
        captive_cable_raw = self._find_vif_decoded_port_field(vif_data, "Captive_Cable") or ""
        text = f"{product_type} {pd_port_type}".strip().lower()

        if "cable" in text:
            port_a_dut = "Cable"
        elif "provider/consumer" in text:
            port_a_dut = "Provider Consumer"
        elif "consumer/provider" in text:
            port_a_dut = "Consumer Provider"
        elif "drp" in text or "dual role" in text:
            port_a_dut = "Dual Role Power[DRP]"
        elif "provider only" in text:
            port_a_dut = "Provider Only"
        elif "consumer only" in text:
            port_a_dut = "Consumer Only"
        else:
            port_a_dut = "Provider Only"

        port_b_dut = "Provider Only"
        state_machine_type = "SRC"
        captive_norm = str(captive_cable_raw).strip().lower()
        is_captive = captive_norm in {"1", "true", "yes"}
        cable_type = "Captive Cable" if is_captive else "GRL-SPL EPR Test Cable 1"

        name = (vif_file_name or "").strip()
        if not name:
            name = "Load XML VIF File"

        return {
            "vifFileName": name,
            "executionMode": "InformationalMode",
            "rerenderRandomNum": 38,
            "ports": {
                "PortA": {
                    "port": "PortA",
                    "dutType": port_a_dut,
                    "cableType": cable_type,
                    "portLable": "",
                    "stateMachineType": state_machine_type,
                },
                "PortB": {
                    "port": "PortB",
                    "dutType": port_b_dut,
                    "cableType": cable_type,
                    "portLable": "",
                    "stateMachineType": state_machine_type,
                },
            },
        }

    def load_vif(
        self,
        vif_file_path: Optional[str] = None,
        *,
        fetch_testcases_after: bool = True,
        testcases_save_to_disk: bool = True,
    ) -> dict:
        """
        Stage 2 - load VIF.

        Sequence:
          1) Convert VIF XML -> JSON and save converted JSON to disk (for verification)
          2) PutVIFFile (filename-only PUT, fallback to multipart upload on 415)
          3) PutVIFData (JSON body)
          4) PutPortConfigurations (payload derived from converted VIF + HAR constants)
          5) If VIF steps succeed and fetch_testcases_after is True, GetTestCaseList and
             save the received test list (same as get_testcases_list). Those fields are
             merged into this return dict (testCasesListSuccess, testCaseCount, paths).
        """
        from vif import VifFramework, XMLProcessor

        vif_framework = VifFramework(config_manager=self._config_manager, logger=self.logger)
        resolved_vif_path = (vif_file_path or vif_framework.get_selected_vif_file() or "").strip()
        if vif_file_path and resolved_vif_path and not os.path.isabs(resolved_vif_path):
            resolved_vif_path = os.path.join(vif_framework.get_vif_dir(), resolved_vif_path)
        if not resolved_vif_path or not os.path.isfile(resolved_vif_path):
            return {
                "success": False,
                "vifFilePath": resolved_vif_path or None,
                "message": "Selected VIF XML file not found. Check common.selectedVifFile and common.vifDir in config.",
            }

        vif_dir = vif_framework.get_vif_dir()
        base_name = os.path.splitext(os.path.basename(resolved_vif_path))[0]

        try:
            vif_data = XMLProcessor(resolved_vif_path).process_xml()
        except Exception as e:
            return {
                "success": False,
                "vifFilePath": resolved_vif_path,
                "message": f"VIF XML to JSON conversion failed: {e}",
            }

        try:
            vif_framework.ensure_vif_dir()
            converted_json_path = os.path.join(vif_dir, base_name + "_vif_data.json")
            with open(converted_json_path, "w", encoding="utf-8") as f:
                json.dump(vif_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            converted_json_path = None
            self.logger.warning("[vif] Could not save converted JSON: %s", e)
        if converted_json_path:
            print(f"  VIF: JSON saved for verification: {converted_json_path}", file=sys.stderr, flush=True)

        vif_filename = os.path.basename(resolved_vif_path)
        put_file_res = self.call_api(ApiName.VIF_PATH, path_suffix=vif_filename)
        if put_file_res.is_success:
            put_vif_file_result = put_file_res
            put_file_attempt = "filename-only"
        else:
            err = (put_file_res.error or "").lower()
            if "415" in err or "unsupported media type" in err or "media type" in err:
                put_file_res = self.call_api(ApiName.VIF_PATH, vif_file_path=resolved_vif_path)
                put_file_attempt = "multipart"
            else:
                put_file_attempt = "filename-only"
            put_vif_file_result = put_file_res
        if put_vif_file_result.is_success:
            if put_file_attempt == "multipart":
                print(f"  VIF: file uploaded ({vif_filename})", file=sys.stderr, flush=True)
            else:
                print(f"  VIF: filename sent for report folder ({vif_filename})", file=sys.stderr, flush=True)

        put_vif_data_res = self.call_api(ApiName.PUT_VIF_DATA, data=vif_data, path_suffix="PortA")

        port_config_payload = self._build_port_config_from_vif(vif_data, vif_filename)
        put_port_cfg_res = self.call_api(ApiName.PUT_PORT_CONFIGURATIONS, data=port_config_payload)

        ok = bool(put_vif_file_result.is_success and put_vif_data_res.is_success and put_port_cfg_res.is_success)
        if ok:
            print("  VIF: PutVIFData + PutPortConfigurations done.", file=sys.stderr, flush=True)

        testcases_list_fetch = None
        if ok and fetch_testcases_after:
            if hasattr(self, "get_testcases_list"):
                testcases_list_fetch = self.get_testcases_list(save_to_disk=testcases_save_to_disk)
                if not testcases_list_fetch.get("success"):
                    self.logger.warning(
                        "[vif] Test case list fetch after VIF load did not succeed: %s",
                        testcases_list_fetch.get("message"),
                    )
            else:
                testcases_list_fetch = {
                    "success": False,
                    "message": "get_testcases_list not available on this client instance.",
                }

        payload = {
            "success": ok,
            "vifFilePath": resolved_vif_path,
            "vifFileName": vif_filename,
            "convertedVifJsonPath": converted_json_path,
            "putVIFFile": api_result_to_json_dict(put_vif_file_result),
            "putVIFFileAttempt": put_file_attempt,
            "putVIFData": api_result_to_json_dict(put_vif_data_res),
            "putPortConfigurations": api_result_to_json_dict(put_port_cfg_res),
        }
        if testcases_list_fetch is not None:
            tc = testcases_list_fetch
            payload["testCasesListSuccess"] = bool(tc.get("success"))
            payload["testCaseCount"] = int(tc.get("testCaseCount") or 0)
            if tc.get("testCasesJsonPath") is not None:
                payload["testCasesJsonPath"] = tc["testCasesJsonPath"]
            if tc.get("testCasesRawJsonPath") is not None:
                payload["testCasesRawJsonPath"] = tc["testCasesRawJsonPath"]
            msg = tc.get("message")
            if msg:
                payload["testCasesListMessage"] = msg
        return payload
