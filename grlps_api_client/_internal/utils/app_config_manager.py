"""
GRLPS app configuration manager.
Loads grlps_app_config.json and provides
selectedApp, common settings, and per-application settings (C2-EPR now; C3 later).
"""

import os
from typing import Any, Dict, Optional
import logging

from json_reader import JSONConfigError, JSONReader, load_json_file


class AppConfigManager:
    """
    Loads app config from JSON file only (no built-in fallback).
    Exposes get_common(), get_selected_app(), get_app(), get_app_field(), get_base_url().
    """

    def __init__(self, config_file_path: str, logger: Optional[logging.Logger] = None):
        self.config_file_path = config_file_path
        self.logger = logger or logging.getLogger("AppConfigManager")
        self.config_data: Dict[str, Any] = {}
        self._reader: Optional[JSONReader] = None

        if not os.path.isfile(config_file_path):
            raise FileNotFoundError("Required app config not found: {0}".format(config_file_path))
        try:
            self.config_data = load_json_file(config_file_path)
            self.logger.info("App config loaded: %s", config_file_path)
        except JSONConfigError as e:
            self.logger.error("App config load failed: %s", e)
            if e.cause:
                self.logger.debug("Cause: %s", e.cause)
            raise

        self._reader = JSONReader(self.config_data)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get value by dot path (e.g. 'common.apiTimeout', 'applications.C2-EPR.known_port')."""
        return self._reader.get(key_path, default)

    def get_section(self, section_path: str) -> Dict[str, Any]:
        """Get entire section as dict (e.g. 'common', 'applications.C2-EPR')."""
        return self._reader.get(section_path, {}) or {}

    def set_logger(self, logger: logging.Logger) -> None:
        """Update logger instance (e.g. after bootstrap creates session_logger)."""
        self.logger = logger

    def get_common(self) -> Dict[str, Any]:
        """Return the common section (initialWait, maxConnectionAttempts, connectionTimeout, apiTimeout)."""
        return self.get_section("common")

    def get_selected_app(self) -> str:
        """Return selectedApp key (e.g. 'C2-EPR')."""
        return self.get("selectedApp", "C2-EPR")

    def get_app(self, app_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Return full application dict. If app_key is None, use selectedApp.
        Returns {} if app not found.
        """
        key = app_key or self.get_selected_app()
        if not key:
            return {}
        return self.get_section("applications.{0}".format(key))

    def get_app_field(self, field: str, default: Any = None, app_key: Optional[str] = None) -> Any:
        """Get a single field from the selected (or given) application."""
        app = self.get_app(app_key)
        return app.get(field, default)

    def get_base_url(self, app_key: Optional[str] = None) -> str:
        """Build base URL from ip_address and known_port for the selected (or given) app."""
        app = self.get_app(app_key)
        ip = app.get("ip_address", "localhost")
        port = app.get("known_port", 5001)
        return "http://{0}:{1}".format(ip, port)
