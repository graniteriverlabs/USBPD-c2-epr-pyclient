"""
Logging configuration manager.
Loads logging config from JSON (with logging and fallback) and provides per-role config for LogManager.
File loading, logging, and default fallback live here; json_reader package handles all JSON file errors.
"""

import copy
import os
from typing import Dict, Any, Optional
import logging

from json_reader import JSONConfigError, JSONReader, load_json_file
from .logging_defaults import DEFAULT_LOGGING_CONFIG


def _resolve_project_root_from_file(file_path: str) -> str:
    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


class LoggingConfigManager:
    """Loads logging config from JSON file or built-in Python defaults; provides get_section, get, etc."""

    def __init__(self, config_file_path: str, logger: Optional[logging.Logger] = None):
        self.config_file_path = config_file_path
        self.logger = logger or logging.getLogger("LoggingConfigManager")
        self.config_data: Dict[str, Any] = {}
        self._reader: JSONReader

        if os.path.isfile(config_file_path):
            try:
                self.config_data = load_json_file(config_file_path)
                self.logger.info("Config loaded: %s", config_file_path)
            except JSONConfigError as e:
                self.logger.error("Config load failed: %s", e)
                if e.cause:
                    self.logger.debug("Cause: %s", e.cause)
                self.config_data = copy.deepcopy(DEFAULT_LOGGING_CONFIG)
                self.logger.info("Using built-in defaults")
        else:
            self.config_data = copy.deepcopy(DEFAULT_LOGGING_CONFIG)
            self.logger.info(
                "No logging config file at %s; using built-in defaults",
                config_file_path,
            )

        self._reader = JSONReader(self.config_data)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get value by dot path (delegate to reader)."""
        return self._reader.get(key_path, default)

    def get_section(self, section_path: str) -> Dict[str, Any]:
        """Get entire section (delegate to reader)."""
        return self._reader.get_section(section_path)

    def set_logger(self, logger: logging.Logger) -> None:
        """Update logger instance (e.g. after bootstrap creates session_logger)."""
        self.logger = logger

    def get_default_config(self) -> Dict[str, Any]:
        """Return the default logging section (default)."""
        return self.get_section("default")

    def get_environment_config(self, env: str) -> Dict[str, Any]:
        """Return environment overrides (e.g. development, production, testing)."""
        return self.get("environments.{0}".format(env), {})

    def get_format(self, format_name: str) -> str:
        """Return a named format string from config.formats."""
        return self.get(
            "formats.{0}".format(format_name),
            "%(asctime)s - %(levelname)s - %(message)s",
        )

    def get_logging_config_for_app(self, role: str) -> Dict[str, Any]:
        """
        Return full logging config for a role (e.g. 'session', 'default').
        Merges default with the role section, resolves log path, ensures directory exists.
        Returned dict is suitable for LogManager.from_config().
        """
        default = self.get_default_config()
        if not default:
            default = {
                "logFilename": "api_framework.log",
                "logDirectory": "logs",
                "logLevel": "INFO",
                "logToConsole": True,
                "maxLogSizeMb": 10,
                "backupCount": 5,
                "rotationType": "size",
                "logMode": "a",
                "loggerName": "ApiFramework",
            }

        config = default.copy()
        section = self.get_section(role)
        if section:
            config.update(section)

        log_directory = config.get("logDirectory", "logs")
        if not os.path.isabs(log_directory):
            base_dir = _resolve_project_root_from_file(__file__)
            log_directory = os.path.join(base_dir, log_directory)
        log_directory = os.path.normpath(log_directory)
        os.makedirs(log_directory, exist_ok=True)

        log_filename = config.get("logFilename", "api_framework.log")
        if not os.path.isabs(log_filename):
            log_filename = os.path.join(log_directory, log_filename)
        config["logFilename"] = log_filename

        return config
