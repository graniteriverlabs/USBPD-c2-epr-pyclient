"""Stage-2 project folder + VIF load (PutProjectFolder, PutVIFFile, PutVIFData, PutPortConfigurations)."""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

from api import ApiName
from api.result import api_result_to_json_dict

PORT_CONFIG_MAPPING_FILE = "config/put_port_config_mapping.json"

# Bump whenever the shipped mapping's values change. c2epr-init never overwrites
# an existing workspace file, so a workspace created by an earlier release keeps
# its old copy; comparing versions is what tells the user it is out of date.
PORT_CONFIG_MAPPING_VERSION = "1.1"

# Levels the mapping file may name in onMissingCaptiveCable.logLevel.
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Used only when config/put_port_config_mapping.json cannot be read. Kept in step
# with that file; both mirror the requests the C2-EPR application itself sends.
BUILTIN_PORT_CONFIG_MAPPING: Dict[str, Any] = {
    "defaults": {
        "executionMode": "InformationalMode",
        "rerenderRandomNum": 38,
        "portLabel": "",
        "stateMachineType": "SRC",
        "portBDutType": "Provider Only",
        "fallbackCableType": "GRL-SPL EPR Test Cable 1",
    },
    "portADutTypeRules": [
        {"matchContainsAny": ["cable"], "result": "Cable"},
        {"matchContainsAny": ["provider/consumer"], "result": "Provider Consumer"},
        {"matchContainsAny": ["consumer/provider"], "result": "Consumer Provider"},
        {"matchContainsAny": ["drp", "dual role"], "result": "Dual Role Power[DRP]"},
        {"matchContainsAny": ["provider only"], "result": "Provider Only"},
        {"matchContainsAny": ["consumer only"], "result": "Consumer Only"},
    ],
    "portADutTypeFallback": "Provider Only",
    "requiredInputValidation": {
        "requireCaptiveCableField": True,
        "onMissingCaptiveCable": {
            "logLevel": "WARNING",
            "message": (
                "VIF XML field 'Captive_Cable' is missing, so the cable selection "
                "cannot be derived from the VIF."
            ),
        },
    },
    "cableTypeByScenario": [
        {
            "category": "cable",
            "captiveCable": False,
            "portA": "No Cable ( For Cable Testing )",
            "portB": "GRL-SPL EPR Test Cable 1",
        },
        {
            "category": "cable",
            "captiveCable": True,
            "portA": "No Cable ( For Cable Testing )",
            "portB": "GRL-SPL EPR Test Cable 1",
        },
        {
            "category": "normal",
            "captiveCable": True,
            "portA": "Captive Cable",
            "portB": "GRL-SPL EPR Test Cable 1",
        },
        {
            "category": "normal",
            "captiveCable": False,
            "portA": "GRL-SPL EPR Test Cable 1",
            "portB": "GRL-SPL EPR Test Cable 1",
        },
    ],
    "categoryDetection": {"cableCategoryContainsAny": ["cable"]},
}


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

    def _port_config_mapping_path(self) -> str:
        """Location of the PutPortConfigurations mapping file (config override allowed)."""
        try:
            common = self._get_common() or {}
        except Exception:
            common = {}
        configured = str(common.get("portConfigMappingFile") or "").strip()
        path = configured or PORT_CONFIG_MAPPING_FILE
        if os.path.isabs(path):
            return os.path.normpath(path)
        root_fn = getattr(self, "_project_root", None)
        root = root_fn() if callable(root_fn) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # normpath so the path printed to the user uses one separator style.
        return os.path.normpath(os.path.join(root, path))

    def _get_port_config_mapping(self) -> Dict[str, Any]:
        """
        Load the PutPortConfigurations mapping, cached for the life of the client.

        The mapping lives in config so the cable and DUT type tables can be
        corrected without a code change. Falls back to the built-in copy when the
        file is missing or unreadable, so a damaged config cannot stop a run.
        """
        cached = getattr(self, "_port_config_mapping_cache", None)
        if cached is not None:
            return cached

        mapping = None
        path = self._port_config_mapping_path()
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                section = loaded.get("putPortConfigurations") if isinstance(loaded, dict) else None
                if isinstance(section, dict) and section:
                    mapping = section
                    file_version = str((loaded.get("version") or "")).strip()
                    if file_version != PORT_CONFIG_MAPPING_VERSION:
                        warning = (
                            "{0} is version '{1}', but this release ships version '{2}'. "
                            "It was kept because c2epr-init never overwrites your files. "
                            "If you have not edited it, delete it and run c2epr-init to "
                            "pick up the corrected cable selection table.".format(
                                path, file_version or "unknown", PORT_CONFIG_MAPPING_VERSION
                            )
                        )
                        self.logger.warning("[vif] %s", warning)
                        print(f"  VIF: {warning}", file=sys.stderr, flush=True)
                else:
                    self.logger.warning(
                        "[vif] %s has no usable 'putPortConfigurations' section; using built-in mapping.",
                        path,
                    )
            except Exception as e:
                self.logger.warning("[vif] Could not read %s (%s); using built-in mapping.", path, e)
        else:
            self.logger.warning("[vif] Port config mapping not found at %s; using built-in mapping.", path)

        if mapping is None:
            mapping = BUILTIN_PORT_CONFIG_MAPPING
        self._port_config_mapping_cache = mapping
        return mapping

    def _resolve_port_a_dut_type(self, mapping: Dict[str, Any], text: str) -> str:
        """First rule whose match text appears in 'Product_Type PD_Port_Type' wins."""
        for rule in mapping.get("portADutTypeRules") or []:
            if not isinstance(rule, dict):
                continue
            for needle in rule.get("matchContainsAny") or []:
                needle = str(needle).strip().lower()
                if needle and needle in text:
                    result = str(rule.get("result") or "").strip()
                    if result:
                        return result
        return str(mapping.get("portADutTypeFallback") or "Provider Only")

    def _resolve_cable_types(
        self,
        mapping: Dict[str, Any],
        category: str,
        is_captive: bool,
    ) -> tuple:
        """Cable selection for (PortA, PortB) from the scenario table."""
        fallback = str(
            (mapping.get("defaults") or {}).get("fallbackCableType")
            or "GRL-SPL EPR Test Cable 1"
        )
        for row in mapping.get("cableTypeByScenario") or []:
            if not isinstance(row, dict):
                continue
            if str(row.get("category") or "").strip().lower() != category:
                continue
            if bool(row.get("captiveCable")) != is_captive:
                continue
            return (str(row.get("portA") or fallback), str(row.get("portB") or fallback))
        self.logger.warning(
            "[vif] No cable mapping for category=%s captiveCable=%s; using %r for both ports.",
            category,
            is_captive,
            fallback,
        )
        return (fallback, fallback)

    def _build_port_config_from_vif(self, vif_data: Dict[str, Any], vif_file_name: str) -> Dict[str, Any]:
        """
        Build the PutPortConfigurations payload, driven by config/put_port_config_mapping.json.

        - vifFileName is the loaded VIF basename, same as PutVIFFile
        - PortA dutType comes from Product_Type / PD_Port_Type via the rule table
        - PortB is the tester's own port: dutType and cableType are constants
        - PortA cableType depends on BOTH the DUT category and Captive_Cable. A
          cable DUT is the only cable in the path, so it reports no test cable;
          deriving this from Captive_Cable alone sent a test cable that is not
          physically there and left cable runs incomplete.
        """
        mapping = self._get_port_config_mapping()
        defaults = mapping.get("defaults") or {}

        pd_port_type = self._find_vif_decoded_port_field(vif_data, "PD_Port_Type") or ""
        product_type = self._find_vif_decoded_port_field(vif_data, "Product_Type") or ""
        captive_cable_raw = self._find_vif_decoded_port_field(vif_data, "Captive_Cable")
        text = f"{product_type} {pd_port_type}".strip().lower()

        port_a_dut = self._resolve_port_a_dut_type(mapping, text)

        # Category decides the cable selection together with the captive flag.
        # Cable VIFs carry no Captive_Cable field, so the category has to be read
        # from the DUT itself rather than inferred from that flag.
        cable_needles = [
            str(n).strip().lower()
            for n in (mapping.get("categoryDetection") or {}).get("cableCategoryContainsAny") or []
            if str(n).strip()
        ]
        is_cable_dut = port_a_dut.strip().lower() == "cable" or any(n in text for n in cable_needles)
        category = "cable" if is_cable_dut else "normal"

        captive_present = captive_cable_raw is not None and str(captive_cable_raw).strip() != ""
        is_captive = str(captive_cable_raw or "").strip().lower() in {"1", "true", "yes"}

        cable_type_a, cable_type_b = self._resolve_cable_types(mapping, category, is_captive)

        notes = []
        # Missing Captive_Cable is normal for a cable DUT and only ambiguous
        # elsewhere, where the flag is what picks the cable.
        validation = mapping.get("requiredInputValidation") or {}
        if not captive_present and not is_cable_dut and bool(validation.get("requireCaptiveCableField", True)):
            on_missing = validation.get("onMissingCaptiveCable") or {}
            note = "{0} Using {1!r} for PortA.".format(
                on_missing.get("message")
                or "VIF XML field 'Captive_Cable' is missing, so the cable selection cannot be derived from the VIF.",
                cable_type_a,
            )
            notes.append(note)
            level = str(on_missing.get("logLevel") or "WARNING").strip().upper()
            self.logger.log(logging.getLevelName(level) if level in _LOG_LEVELS else logging.WARNING, "[vif] %s", note)
            print(f"  VIF: {note}", file=sys.stderr, flush=True)

        self.logger.info(
            "[vif] Port config: category=%s captive=%s (field %s) | "
            "PortA dutType=%r cableType=%r | PortB dutType=%r cableType=%r",
            category,
            is_captive,
            "present" if captive_present else "absent",
            port_a_dut,
            cable_type_a,
            defaults.get("portBDutType") or "Provider Only",
            cable_type_b,
        )
        self._last_port_config_notes = notes

        name = (vif_file_name or "").strip()
        if not name:
            name = "Load XML VIF File"

        state_machine_type = str(defaults.get("stateMachineType") or "SRC")
        port_label = str(defaults.get("portLabel") or "")

        return {
            "vifFileName": name,
            "executionMode": str(defaults.get("executionMode") or "InformationalMode"),
            "rerenderRandomNum": defaults.get("rerenderRandomNum", 38),
            "ports": {
                "PortA": {
                    "port": "PortA",
                    "dutType": port_a_dut,
                    "cableType": cable_type_a,
                    "portLable": port_label,
                    "stateMachineType": state_machine_type,
                },
                "PortB": {
                    "port": "PortB",
                    "dutType": str(defaults.get("portBDutType") or "Provider Only"),
                    "cableType": cable_type_b,
                    "portLable": port_label,
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
            port_a = port_config_payload["ports"]["PortA"]
            # The cable selection decides whether the run can complete, so show
            # it rather than leaving it to the log.
            print("  VIF: PutVIFData + PutPortConfigurations done.", file=sys.stderr, flush=True)
            print(
                "  VIF: DUT type '{0}', cable selection '{1}'.".format(
                    port_a["dutType"], port_a["cableType"]
                ),
                file=sys.stderr,
                flush=True,
            )

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
            "portADutType": port_config_payload["ports"]["PortA"]["dutType"],
            "portACableType": port_config_payload["ports"]["PortA"]["cableType"],
            "portBCableType": port_config_payload["ports"]["PortB"]["cableType"],
        }
        notes = getattr(self, "_last_port_config_notes", None)
        if notes:
            payload["portConfigNotes"] = list(notes)
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
