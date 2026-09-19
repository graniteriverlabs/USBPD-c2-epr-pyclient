"""
Unified configuration manager: logging and GRLPS app config.
Loads logging_config.json and (optionally) grlps_app_config.json; exposes both.
"""

from typing import Any, Dict, Optional
import logging

from .logging_config_manager import LoggingConfigManager
from .app_config_manager import AppConfigManager


class UnifiedConfigManager:
    """
    Single entry for configuration: logging + app config.
    When app_config_file is provided, loads grlps_app_config and exposes app getters.
    """

    def __init__(
        self,
        logging_config_file: str,
        app_config_file: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("UnifiedConfigManager")
        self.logging_config = LoggingConfigManager(logging_config_file, self.logger)
        self._app_config: Optional[AppConfigManager] = None
        if app_config_file:
            self._app_config = AppConfigManager(app_config_file, self.logger)

    def get_logging_config_for_app(self, role: str) -> Dict[str, Any]:
        """Return logging config dict for the given role (e.g. 'session', 'default')."""
        return self.logging_config.get_logging_config_for_app(role)

    def set_logger(self, logger: logging.Logger) -> None:
        """Use this logger for all config manager logging."""
        self.logger = logger
        self.logging_config.set_logger(logger)
        if self._app_config:
            self._app_config.set_logger(logger)

    # --- App config (delegate to AppConfigManager when loaded) ---
    def get_common(self) -> Dict[str, Any]:
        """Return common app settings (initialWait, maxConnectionAttempts, connectionTimeout, apiTimeout)."""
        return self._app_config.get_common() if self._app_config else {}

    def get_selected_app(self) -> Optional[str]:
        """Return selectedApp key (e.g. 'C2-EPR'). None if app config not loaded."""
        return self._app_config.get_selected_app() if self._app_config else None

    def get_app(self, app_key: Optional[str] = None) -> Dict[str, Any]:
        """Return full application dict for selected app (or app_key). {} if app config not loaded."""
        return self._app_config.get_app(app_key) if self._app_config else {}

    def get_app_field(self, field: str, default: Any = None, app_key: Optional[str] = None) -> Any:
        """Get a single field from the selected (or given) application."""
        return (
            self._app_config.get_app_field(field, default, app_key)
            if self._app_config
            else default
        )

    def get_base_url(self, app_key: Optional[str] = None) -> str:
        """Build base URL (http://ip:port) for the selected (or given) app. Empty string if app config not loaded."""
        return self._app_config.get_base_url(app_key) if self._app_config else ""
