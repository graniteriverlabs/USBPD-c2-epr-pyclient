"""
Report framework service:
- wraps ReportsGeneration APIs
- builds report URL
- copies report artifacts to user-configured destination
"""

import os
import shutil
import time
from typing import Any, Dict, Optional

from api import ApiName
from api.result import api_result_to_json_dict


class ReportFrameworkService:
    def __init__(self, core):
        self._core = core

    def _extract_response_data(self, payload: Dict[str, Any]) -> Any:
        """
        Extract API response.data from normalized payload shape.
        Handles both:
          - {"data": {"response": {"data": ...}}}
          - {"data": {"data": {"response": {"data": ...}}}}
        """
        data_obj = payload.get("data")
        if not isinstance(data_obj, dict):
            return None
        if isinstance(data_obj.get("response"), dict):
            return data_obj.get("response", {}).get("data")
        nested = data_obj.get("data")
        if isinstance(nested, dict) and isinstance(nested.get("response"), dict):
            return nested.get("response", {}).get("data")
        return None

    def get_report_inputs(self) -> Dict[str, Any]:
        result = self._core.call_api(ApiName.GET_REPORT_INPUTS)
        return api_result_to_json_dict(result)

    def update_report_inputs(self, report_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = report_inputs or {}
        result = self._core.call_api(ApiName.POST_UPDATE_REPORT_INPUTS, data=payload)
        return api_result_to_json_dict(result)

    def get_test_run_info(self) -> Dict[str, Any]:
        result = self._core.call_api(ApiName.GET_TEST_RUN_INFO)
        return api_result_to_json_dict(result)

    def get_results_folder_name(self) -> Dict[str, Any]:
        result = self._core.call_api(ApiName.GET_RESULTS_FOLDER_NAME)
        return api_result_to_json_dict(result)

    def get_report_file_name(self) -> Dict[str, Any]:
        result = self._core.call_api(ApiName.GET_REPORT_FILE_NAME)
        return api_result_to_json_dict(result)

    def get_report_path_status(self) -> Dict[str, Any]:
        result = self._core.call_api(ApiName.GET_REPORT_PATH_STATUS)
        return api_result_to_json_dict(result)

    def build_report_url(self, report_file_name: Optional[str] = None) -> str:
        file_name = report_file_name
        if not file_name:
            file_payload = self.get_report_file_name()
            file_name = self._extract_response_data(file_payload)
        if not file_name:
            return ""
        base_url = (self._core.get_base_url() or "").rstrip("/")
        if not base_url:
            return ""
        return f"{base_url}/Report/{file_name}"

    def run_report_flow(
        self,
        report_inputs: Optional[Dict[str, Any]] = None,
        *,
        copy_run_folder: bool = False,
    ) -> Dict[str, Any]:
        self._core.logger.info("[report_flow] starting report workflow")
        update_payload = self.update_report_inputs(report_inputs=report_inputs or {})
        inputs_payload = self.get_report_inputs()
        run_info_payload = self.get_test_run_info()
        folder_payload = self.get_results_folder_name()
        file_payload = self.get_report_file_name()
        path_status_payload = self.get_report_path_status()

        report_file_name = self._extract_response_data(file_payload)
        results_folder_name = self._extract_response_data(folder_payload)
        report_url = ""
        if report_file_name:
            base_url = (self._core.get_base_url() or "").rstrip("/")
            if base_url:
                report_url = f"{base_url}/Report/{report_file_name}"
        export_payload = self._copy_report_artifacts(
            run_info_payload=run_info_payload,
            results_folder_name=results_folder_name,
            report_file_name=report_file_name,
            copy_run_folder=copy_run_folder,
        )
        self._core.logger.info(
            "[report_flow] sourceFolder=%s | runRootFolder=%s",
            export_payload.get("sourceFolder"),
            export_payload.get("resolvedRunFolder"),
        )
        run_root_folder = export_payload.get("resolvedRunFolder")
        if run_root_folder:
            self._core.logger.info(
                "[report_flow] You can find more reports at the following location: %s",
                run_root_folder,
            )
        self._core.logger.info(
            "[report_flow] completed | reportFile=%s | reportUrl=%s | exportSuccess=%s | destination=%s",
            report_file_name,
            report_url,
            export_payload.get("success"),
            export_payload.get("destination"),
        )

        return {
            "updateReportInputs": update_payload,
            "getReportInputs": inputs_payload,
            "getTestRunInfo": run_info_payload,
            "getResultsFolderName": folder_payload,
            "getReportFileName": file_payload,
            "getReportPathStatus": path_status_payload,
            "reportUrl": report_url,
            "reportExport": export_payload,
            "reportSourceFolder": export_payload.get("sourceFolder"),
            "reportRunRootFolder": export_payload.get("resolvedRunFolder"),
            "reportDataHint": "Use reportSourceFolder/reportRunRootFolder to access full generated artifacts on disk.",
            "timestamp": int(time.time()),
        }

    def _get_report_export_dir(self) -> str:
        common = self._core._get_common() or {}
        path = str(common.get("reportExportDir") or "").strip()
        if not path:
            return ""
        if not os.path.isabs(path):
            # A relative export path belongs to the workspace. Resolving it
            # against the current directory instead would scatter reports
            # wherever the command happened to be launched from.
            return os.path.abspath(os.path.join(self._core._project_root(), path))
        return os.path.abspath(path)

    def _fallback_export_dir(self) -> str:
        """
        Safe internal fallback when end-user export path is missing/invalid.
        """
        root = self._core._project_root()
        return os.path.join(root, "user_interaction", "reports_export")

    def _ensure_writable_dir(self, path: str) -> bool:
        """
        Validate that directory exists (or can be created) and is writable.
        """
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".write_probe.tmp")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return True
        except Exception:
            return False

    def _resolve_report_source_folder(
        self, run_info_payload: Dict[str, Any], results_folder_name: Optional[str]
    ) -> str:
        entries = self._extract_response_data(run_info_payload)
        if isinstance(entries, list):
            # 1) Prefer exact match when TestRunInfo already includes the requested folder.
            if results_folder_name:
                suffix = "\\" + str(results_folder_name).strip("\\/")
                for row in entries:
                    if not isinstance(row, dict):
                        continue
                    full_path = str(row.get("resultsFolder") or "").strip()
                    if full_path and full_path.lower().endswith(suffix.lower()):
                        return full_path

                # 2) If exact folder is not listed yet, infer the common root from any
                # run-info entry and combine it with GetResultsFolderName.
                for row in entries:
                    if not isinstance(row, dict):
                        continue
                    full_path = str(row.get("resultsFolder") or "").strip()
                    if not full_path:
                        continue
                    base_root = os.path.dirname(full_path.rstrip("\\/"))
                    if base_root:
                        inferred = os.path.join(base_root, str(results_folder_name).strip("\\/"))
                        self._core.logger.info(
                            "[report_export] inferred source folder from run-info root: %s",
                            inferred,
                        )
                        return inferred

            # 3) Last fallback: use first run-info entry if caller did not provide folder name.
            for row in entries:
                if not isinstance(row, dict):
                    continue
                full_path = str(row.get("resultsFolder") or "").strip()
                if full_path:
                    return full_path
        return ""

    def _resolve_existing_source_folder(
        self, run_info_payload: Dict[str, Any], preferred_folder: str
    ) -> str:
        """
        Ensure selected source folder exists. If not, fallback to latest existing
        folder from GetTestRunInfo entries.
        """
        if preferred_folder and os.path.isdir(preferred_folder):
            return preferred_folder
        entries = self._extract_response_data(run_info_payload)
        if isinstance(entries, list):
            existing = []
            for row in entries:
                if not isinstance(row, dict):
                    continue
                full_path = str(row.get("resultsFolder") or "").strip()
                if full_path and os.path.isdir(full_path):
                    existing.append(full_path)
            if existing:
                existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                fallback = existing[0]
                self._core.logger.info(
                    "[report_export] preferred source folder missing; using latest existing run folder: %s",
                    fallback,
                )
                return fallback
        return preferred_folder

    def _copy_report_artifacts(
        self,
        run_info_payload: Dict[str, Any],
        results_folder_name: Optional[str],
        report_file_name: Optional[str],
        *,
        copy_run_folder: bool = False,
    ) -> Dict[str, Any]:
        requested_export_dir = self._get_report_export_dir()
        export_dir = requested_export_dir
        if not export_dir or not self._ensure_writable_dir(export_dir):
            export_dir = self._fallback_export_dir()
            if not self._ensure_writable_dir(export_dir):
                return {
                    "enabled": True,
                    "success": False,
                    "destination": requested_export_dir,
                    "fallbackDestination": export_dir,
                    "message": "Configured reportExportDir is invalid/unwritable and fallback path is also unavailable.",
                }
            self._core.logger.warning(
                "[report_export] Invalid/unwritable reportExportDir '%s'; using fallback '%s'",
                requested_export_dir,
                export_dir,
            )

        source_folder = self._resolve_report_source_folder(run_info_payload, results_folder_name)
        source_folder = self._resolve_existing_source_folder(run_info_payload, source_folder)
        if not source_folder:
            self._core.logger.warning(
                "[report_export] Could not resolve source folder from API payloads. "
                "resultsFolderName='%s'. Verify report APIs returned run info/results folder.",
                results_folder_name,
            )
            return {
                "enabled": True,
                "success": False,
                "destination": export_dir,
                "requestedDestination": requested_export_dir,
                "message": "Could not resolve source report folder from API payloads.",
            }
        if not os.path.isdir(source_folder):
            self._core.logger.warning(
                "[report_export] Resolved source folder does not exist on disk: %s",
                source_folder,
            )
            return {
                "enabled": True,
                "success": False,
                "destination": export_dir,
                "requestedDestination": requested_export_dir,
                "sourceFolder": source_folder,
                "message": "Resolved source report folder does not exist on disk.",
            }

        effective_source_folder = source_folder
        if report_file_name:
            root_html = os.path.join(source_folder, str(report_file_name))
            if not os.path.isfile(root_html):
                # In many C2 runs, report html lives under a nested folder like
                # New_Run1_Rep0_<timestamp>. Auto-detect it from child folders.
                candidate_folders = []
                try:
                    for name in os.listdir(source_folder):
                        full = os.path.join(source_folder, name)
                        if os.path.isdir(full):
                            candidate_folders.append(full)
                except Exception:
                    candidate_folders = []

                for child in candidate_folders:
                    child_html = os.path.join(child, str(report_file_name))
                    if os.path.isfile(child_html):
                        effective_source_folder = child
                        self._core.logger.info(
                            "[report_export] using nested report folder: %s",
                            effective_source_folder,
                        )
                        break

                if effective_source_folder == source_folder:
                    prefixed = [
                        p
                        for p in candidate_folders
                        if os.path.basename(p).lower().startswith("new_run")
                    ]
                    if prefixed:
                        prefixed.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                        effective_source_folder = prefixed[0]
                        self._core.logger.info(
                            "[report_export] fallback to latest nested New_Run folder: %s",
                            effective_source_folder,
                        )

        run_name = os.path.basename(effective_source_folder.rstrip("\\/"))
        run_dest = os.path.join(export_dir, run_name)
        html_copied = None
        pdf_copied = None
        try:
            os.makedirs(export_dir, exist_ok=True)
            # If destination root already equals source parent, files are already in place.
            src_parent = os.path.abspath(os.path.dirname(effective_source_folder.rstrip("\\/")))
            if os.path.abspath(export_dir) == src_parent:
                return {
                    "enabled": True,
                    "success": True,
                    "destination": export_dir,
                    "requestedDestination": requested_export_dir,
                    "sourceFolder": effective_source_folder,
                    "resolvedRunFolder": source_folder,
                    "copiedRunFolder": effective_source_folder if copy_run_folder else None,
                    "copiedReportHtml": os.path.join(effective_source_folder, str(report_file_name)) if report_file_name else None,
                    "copiedReportPdf": None,
                    "message": "Destination equals report source root; folder copy skipped.",
                }
            if copy_run_folder:
                # Never delete an existing export. Run folder names carry a
                # timestamp, so a collision means the same run is being exported
                # twice and overwriting those files is harmless; wiping the
                # directory first would also destroy anything else kept there.
                shutil.copytree(effective_source_folder, run_dest, dirs_exist_ok=True)

            if report_file_name:
                src_html = os.path.join(effective_source_folder, str(report_file_name))
                if os.path.isfile(src_html):
                    # Reports go under export_dir/<run folder>/ rather than
                    # straight into export_dir. The application reuses report
                    # file names across runs (Run_1 restarts with each new
                    # project), so a flat copy silently replaced the previous
                    # run's report.
                    os.makedirs(run_dest, exist_ok=True)
                    dst_html = os.path.join(run_dest, str(report_file_name))
                    shutil.copy2(src_html, dst_html)
                    html_copied = dst_html
                    self._core.logger.info("[report_export] copied html: %s", dst_html)

                # Also copy PDF with the same base name when available.
                if str(report_file_name).lower().endswith(".html"):
                    pdf_name = str(report_file_name)[:-5] + ".pdf"
                    src_pdf = os.path.join(effective_source_folder, pdf_name)
                    if os.path.isfile(src_pdf):
                        dst_pdf = os.path.join(run_dest, pdf_name)
                        shutil.copy2(src_pdf, dst_pdf)
                        pdf_copied = dst_pdf
                        self._core.logger.info("[report_export] copied pdf (same basename): %s", dst_pdf)
                    else:
                        # Fallback: some builds generate a differently named PDF.
                        try:
                            pdf_candidates = [
                                name
                                for name in os.listdir(effective_source_folder)
                                if name.lower().endswith(".pdf")
                                and os.path.isfile(os.path.join(effective_source_folder, name))
                            ]
                        except Exception:
                            pdf_candidates = []
                        if pdf_candidates:
                            pdf_candidates.sort()
                            fallback_pdf = pdf_candidates[0]
                            src_pdf = os.path.join(effective_source_folder, fallback_pdf)
                            dst_pdf = os.path.join(run_dest, fallback_pdf)
                            shutil.copy2(src_pdf, dst_pdf)
                            pdf_copied = dst_pdf
                            self._core.logger.info(
                                "[report_export] copied pdf (fallback name): %s",
                                dst_pdf,
                            )
                        else:
                            self._core.logger.info(
                                "[report_export] no pdf found in source folder: %s",
                                effective_source_folder,
                            )

            return {
                "enabled": True,
                "success": True,
                "destination": export_dir,
                "requestedDestination": requested_export_dir,
                "sourceFolder": effective_source_folder,
                "resolvedRunFolder": source_folder,
                "copiedRunFolder": run_dest if copy_run_folder else None,
                "copiedReportHtml": html_copied,
                "copiedReportPdf": pdf_copied,
                "message": (
                    "Report run folder + HTML/PDF copied to destination."
                    if copy_run_folder
                    else "Only report HTML/PDF copied to destination; run folder copy skipped."
                ),
            }
        except Exception as e:
            self._core.logger.warning("[report_export] copy failed: %s", e)
            return {
                "enabled": True,
                "success": False,
                "destination": export_dir,
                "requestedDestination": requested_export_dir,
                "sourceFolder": effective_source_folder,
                "resolvedRunFolder": source_folder,
                "copiedRunFolder": run_dest,
                "message": f"Report artifact copy failed: {e}",
            }
