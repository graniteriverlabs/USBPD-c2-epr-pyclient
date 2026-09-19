"""
Msgbox framework: single entry to start/stop message box monitoring in a separate thread.
Saves message and reply for debugging. Python 3.x only.
Reference: GRLPS_PY_API_C3_ALL popup_framework. File names from config (grlps_app_config.json) like C3.
"""

import os

from .msgbox_monitor import MsgBoxMonitor
from .msgbox_storage import MsgBoxStorage


def _resolve_project_root_from_file(file_path):
    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


def _repo_root():
    """Project root (parent of msgbox package) so output dir is same regardless of cwd."""
    return _resolve_project_root_from_file(__file__)


def _resolve_output_dir(log_dir):
    """If log_dir is relative, resolve against repo root so user_interaction is always in project."""
    if not log_dir:
        return log_dir
    if os.path.isabs(log_dir):
        return log_dir
    return os.path.join(_repo_root(), log_dir)


def _get_msgbox_options_from_config(config_manager):
    """
    Read msgbox log dir and file name from config (common.msgboxLogDir, common.msgboxLogJsonName).
    Same approach as GRLPS_PY_API_C3_ALL (allPopupMsgJsonName from config).
    :param config_manager: object with get_common() returning dict (e.g. UnifiedConfigManager).
    :return: dict with log_dir, log_filename (values may be None to use defaults).
    """
    log_dir = None
    log_filename = None
    if config_manager is not None:
        try:
            common = config_manager.get_common()
            if isinstance(common, dict):
                log_filename = common.get("msgboxLogJsonName")
                log_dir = common.get("msgboxLogDir")
        except Exception:
            pass
    return {"log_dir": log_dir, "log_filename": log_filename}


class MsgBoxFramework(object):
    """
    Main interface for msgbox handling: set API handler, start/stop monitoring.
    All code is in the msgbox folder for easy debugging.
    File name (and optional log dir) can come from config.json (grlps_app_config.json common section).
    """

    def __init__(self, logger=None, log_dir=None, log_filename=None, config_manager=None,
                 poll_interval_sec=0.5, default_response_button="OK"):
        """
        :param logger: Optional logger.
        :param log_dir: Directory for the JSON file. Overridden by config if config_manager given.
        :param log_filename: JSON file name (e.g. "msgbox_log.json"). Overridden by config if config_manager given.
        :param config_manager: If set, log_dir and log_filename are read from config (common.msgboxLogDir,
            common.msgboxLogJsonName). Same approach as GRLPS_PY_API_C3_ALL. Pass the same config used for app (e.g. client.config_manager).
        :param poll_interval_sec: Poll interval in seconds.
        :param default_response_button: Default button to send (e.g. "OK").
        """
        self.logger = logger
        opts = {"log_dir": log_dir, "log_filename": log_filename}
        if config_manager is not None:
            from_config = _get_msgbox_options_from_config(config_manager)
            if from_config.get("log_dir") is not None:
                opts["log_dir"] = _resolve_output_dir(from_config["log_dir"])
            if from_config.get("log_filename") is not None:
                opts["log_filename"] = from_config["log_filename"]
        elif opts.get("log_dir"):
            opts["log_dir"] = _resolve_output_dir(opts["log_dir"])
        self.monitor = MsgBoxMonitor(
            logger=logger,
            log_dir=opts.get("log_dir"),
            log_filename=opts.get("log_filename"),
            poll_interval_sec=poll_interval_sec,
            default_response_button=default_response_button,
        )

    def set_api_handler(self, handler):
        """Set the API handler (GRLPSApiHandler) for GetMessageBox and PutMessageBoxResponse."""
        self.monitor.set_api_handler(handler)
        if self.logger:
            self.logger.info("[msgbox] Framework: API handler set")

    def start_monitoring(self):
        """Start the msgbox monitor thread."""
        self.monitor.start()

    def stop_monitoring(self):
        """Stop the msgbox monitor thread and flush logs."""
        self.monitor.stop()

    def get_storage(self):
        """Return the MsgBoxStorage instance (e.g. to flush or inspect)."""
        return self.monitor.storage

    def get_log_file_path(self):
        """Return the full path where the log file will be saved (for debugging)."""
        return self.monitor.storage._filename
