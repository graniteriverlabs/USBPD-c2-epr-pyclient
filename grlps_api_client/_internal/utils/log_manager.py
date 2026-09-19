"""
Log manager for the API framework.
Handles log file creation, rotation (size or time), and optional console output.
"""

import os
import errno
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional, Dict, Any


class LogManager:
    """
    Manages a single logger: file (with rotation), optional console, level, and format.
    Used by bootstrap to create the session_logger.
    """

    DEFAULT_FORMAT = (
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] [%(threadName)s] - %(message)s"
    )
    SIMPLE_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
    DETAILED_FORMAT = (
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] [%(threadName)s] [%(funcName)s] - %(message)s"
    )

    def __init__(
        self,
        log_filename: str = "api_framework.log",
        logger_name: str = "ApiFramework",
        log_level: int = logging.INFO,
        log_to_console: bool = True,
        max_log_size_mb: int = 10,
        backup_count: int = 3,
        log_mode: str = "a",
        rotation_type: str = "size",
        log_format: Optional[str] = None,
    ):
        """
        Initialize the log manager.

        Args:
            log_filename: Full or relative path to the log file.
            logger_name: Name of the logger instance.
            log_level: e.g. logging.INFO, logging.DEBUG.
            log_to_console: Whether to also log to stderr.
            max_log_size_mb: Max file size in MB before rotation (for size rotation).
            backup_count: Number of rotated files to keep.
            log_mode: 'a' append or 'w' overwrite.
            rotation_type: 'size' or 'time'.
            log_format: Optional format string; uses DEFAULT_FORMAT if None.
        """
        self.log_filename = log_filename
        self.logger_name = logger_name
        self.log_level = log_level
        self.log_to_console = log_to_console
        self.max_log_size_bytes = max_log_size_mb * 1024 * 1024
        self.backup_count = backup_count
        self.log_mode = log_mode
        self.rotation_type = rotation_type
        self.format_string = log_format or self.DEFAULT_FORMAT

        self.logger = self._setup_logger()

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "LogManager":
        """
        Create LogManager from a dict returned by LoggingConfigManager.get_logging_config_for_app.
        Keys: logFilename, loggerName, logLevel (string), logToConsole, maxLogSizeMb,
        backupCount, logMode, rotationType; optional formats.* for log_format.
        """
        log_level = config.get("logLevel", "INFO")
        if isinstance(log_level, str):
            log_level = getattr(logging, log_level.upper(), logging.INFO)

        return cls(
            log_filename=config.get("logFilename", "api_framework.log"),
            logger_name=config.get("loggerName", "ApiFramework"),
            log_level=log_level,
            log_to_console=config.get("logToConsole", True),
            max_log_size_mb=config.get("maxLogSizeMb", 10),
            backup_count=config.get("backupCount", 3),
            log_mode=config.get("logMode", "a"),
            rotation_type=config.get("rotationType", "size"),
            log_format=config.get("logFormat"),
        )

    def _setup_logger(self) -> logging.Logger:
        """Create and configure the logger with file and optional console handlers."""
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(self.log_level)
        logger.handlers.clear()

        formatter = logging.Formatter(self.format_string)

        log_dir = os.path.dirname(self.log_filename)
        if log_dir:
            try:
                try:
                    os.makedirs(log_dir)
                except OSError as e:
                    if getattr(e, "errno", None) != errno.EEXIST:
                        raise
            except Exception as e:
                print("Error creating log directory: {0}".format(e))
                self.log_filename = os.path.basename(self.log_filename)

        try:
            if self.rotation_type.lower() == "time":
                file_handler = TimedRotatingFileHandler(
                    self.log_filename,
                    when="midnight",
                    interval=1,
                    backupCount=self.backup_count,
                    encoding="utf-8",
                )
            else:
                file_handler = RotatingFileHandler(
                    self.log_filename,
                    mode=self.log_mode,
                    maxBytes=self.max_log_size_bytes,
                    backupCount=self.backup_count,
                    encoding="utf-8",
                )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            self._file_handler = file_handler

            if self.log_to_console:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
                self._console_handler = console_handler
        except Exception as e:
            print("Error setting up file logging: {0}".format(e))
            fallback_ok = False
            fallback_path = self._localappdata_fallback_log_path()
            if fallback_path:
                try:
                    os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
                    if self.rotation_type.lower() == "time":
                        file_handler = TimedRotatingFileHandler(
                            fallback_path,
                            when="midnight",
                            interval=1,
                            backupCount=self.backup_count,
                            encoding="utf-8",
                        )
                    else:
                        file_handler = RotatingFileHandler(
                            fallback_path,
                            mode=self.log_mode,
                            maxBytes=self.max_log_size_bytes,
                            backupCount=self.backup_count,
                            encoding="utf-8",
                        )
                    file_handler.setFormatter(formatter)
                    logger.addHandler(file_handler)
                    self._file_handler = file_handler
                    self.log_filename = fallback_path
                    fallback_ok = True
                except Exception as fb_e:
                    print("Error setting up fallback file logging: {0}".format(fb_e))

            if self.log_to_console or not fallback_ok:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
                self._console_handler = console_handler

            if fallback_ok:
                logger.warning(
                    "Primary log path unavailable; using fallback log file at %s",
                    self.log_filename,
                )
            else:
                logger.error("Failed to set up file logging to %s: %s", self.log_filename, e)

        return logger

    def _localappdata_fallback_log_path(self) -> Optional[str]:
        """
        Fallback when install folder is not writable (e.g., Program Files as standard user).
        """
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = os.path.join(os.path.expanduser("~"), "AppData", "Local")
        if not base:
            return None
        fname = os.path.basename(self.log_filename) or "api_framework_session.log"
        return os.path.join(base, "GRLPS", "C2_EPR_Python_Client", "logs", fname)

    def get_logger(self) -> logging.Logger:
        """Return the configured logger instance."""
        return self.logger

    def set_log_level(self, level: int) -> None:
        """Set log level for the logger and all handlers."""
        self.log_level = level
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

    def close(self) -> None:
        """Close all handlers and clear them."""
        for handler in list(self.logger.handlers):
            try:
                handler.close()
                self.logger.removeHandler(handler)
            except Exception as e:
                print("Error closing handler: {0}".format(e))
        self.logger.handlers.clear()
