"""
VIF framework: config-driven VIF directory under user_interaction (same pattern as GRLPS_PY_API_C3_ALL).
VIF files live under user_interaction/vif; selected VIF file path is read from config (grlps_app_config.json common.selectedVifFile).
Reference: MPPGUIform_New.LoadVIFData; C2_API C2Config.VIFfiles; GRLPS_PY_API_C3_ALL user_interaction layout.
"""
from __future__ import print_function

import os

DEFAULT_VIF_DIR = "user_interaction/vif"


def _resolve_project_root_from_file(file_path):
    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


def _repo_root():
    """Project root (parent of vif package) so output dir is same regardless of cwd."""
    return _resolve_project_root_from_file(__file__)


def _resolve_output_dir(vif_dir):
    """If vif_dir is relative, resolve against repo root so user_interaction is always in project."""
    if not vif_dir:
        return vif_dir
    if os.path.isabs(vif_dir):
        return vif_dir
    return os.path.join(_repo_root(), vif_dir)


def _get_vif_options_from_config(config_manager):
    """
    Read VIF dir and selected file from config (common.vifDir, common.selectedVifFile).
    :param config_manager: object with get_common() returning dict (e.g. UnifiedConfigManager).
    :return: dict with vif_dir, selected_vif_file (values may be None).
    """
    vif_dir = None
    selected_vif_file = None
    if config_manager is not None:
        try:
            common = config_manager.get_common()
            if isinstance(common, dict):
                vif_dir = common.get("vifDir")
                selected_vif_file = common.get("selectedVifFile")
        except Exception:
            pass
    return {"vif_dir": vif_dir, "selected_vif_file": selected_vif_file}


class VifFramework(object):
    """
    VIF directory and selected file from config (same type framework as msgbox/test_cases).
    - vifDir: directory under user_interaction for VIF files (e.g. user_interaction/vif).
    - selectedVifFile: path to the selected VIF file (absolute, or relative to repo root / vif dir).
    """

    def __init__(self, vif_dir=None, config_manager=None, logger=None):
        """
        :param vif_dir: Directory for VIF files. Overridden by config if config_manager given.
        :param config_manager: If set, vif_dir and selected_vif_file from config (common.vifDir, common.selectedVifFile).
        :param logger: Optional logger.
        """
        self.logger = logger
        opts = {"vif_dir": vif_dir}
        self._selected_vif_file = None
        if config_manager is not None:
            from_config = _get_vif_options_from_config(config_manager)
            if from_config.get("vif_dir") is not None:
                opts["vif_dir"] = _resolve_output_dir(from_config["vif_dir"])
            if from_config.get("selected_vif_file") is not None:
                self._selected_vif_file = from_config["selected_vif_file"]
        elif opts.get("vif_dir"):
            opts["vif_dir"] = _resolve_output_dir(opts["vif_dir"])
        self._vif_dir = opts.get("vif_dir") or _resolve_output_dir(DEFAULT_VIF_DIR)

    def get_vif_dir(self):
        """Return the resolved VIF directory path (under user_interaction/vif when using config)."""
        return self._vif_dir

    def get_selected_vif_file(self):
        """
        Return the path to the selected VIF file from config (common.selectedVifFile).
        If path is absolute, return as-is. If relative, resolve against VIF dir.
        """
        path = self._selected_vif_file
        if not path:
            return None
        path = path.strip()
        if not path:
            return None
        if os.path.isabs(path):
            return path
        # Relative: resolve against vif dir so "file.xml" or "sub/file.xml" works
        return os.path.join(self._vif_dir, path)

    def ensure_vif_dir(self):
        """Create VIF directory if it does not exist. Returns True if dir exists or was created."""
        try:
            if not os.path.isdir(self._vif_dir):
                os.makedirs(self._vif_dir, exist_ok=True)
                if self.logger:
                    self.logger.info("[vif] Created VIF dir: %s", self._vif_dir)
            return True
        except OSError as e:
            if self.logger:
                self.logger.warning("[vif] Failed to create VIF dir %s: %s", self._vif_dir, e)
            return False

