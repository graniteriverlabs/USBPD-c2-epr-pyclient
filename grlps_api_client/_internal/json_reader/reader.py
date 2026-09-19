"""
JSON file reader with centralized error handling for all JSON file errors.
Handles: file not found, invalid JSON, encoding, permission, and other I/O errors.
Python 3.x only.
"""

import json
from typing import Any, Dict


class JSONConfigError(Exception):
    """
    Raised when a JSON config file cannot be loaded.
    Use .file_path and .cause to debug (e.g. file not found, invalid JSON, permission).
    """

    def __init__(self, message, file_path, cause=None):
        self.message = message
        self.file_path = file_path
        self.cause = cause
        msg = "{0} [path={1}]".format(message, file_path)
        if cause:
            msg += " | cause: {0}".format(cause)
        super().__init__(msg)

    def __str__(self):
        return super().__str__()


def load_json_file(file_path: str) -> Dict[str, Any]:
    """
    Load a JSON file and return its contents as a dict.
    All JSON/file errors are converted to JSONConfigError for consistent handling.

    Raises:
        JSONConfigError: On any of:
            - File not found (FileNotFoundError)
            - Invalid JSON syntax (json.JSONDecodeError)
            - Not a dict after parse (e.g. root is array or string)
            - Permission / access (OSError, PermissionError)
            - Encoding (UnicodeDecodeError)
            - Invalid path type (TypeError)
            - Other I/O (IOError)
    """
    if not isinstance(file_path, str) or not file_path.strip():
        raise JSONConfigError("File path must be a non-empty string", str(file_path), cause=None)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (IOError, OSError) as e:
        raise JSONConfigError("JSON config file not found or cannot read (permission/I/O)", file_path, cause=e)
    except json.JSONDecodeError as e:
        lineno = getattr(e, "lineno", 0)
        colno = getattr(e, "colno", 0)
        msg = getattr(e, "msg", str(e))
        raise JSONConfigError(
            "Invalid JSON in config file (line {0}, col {1}): {2}".format(lineno, colno, msg),
            file_path,
            cause=e,
        )
    except UnicodeDecodeError as e:
        raise JSONConfigError("Config file is not valid UTF-8", file_path, cause=e)
    except TypeError as e:
        raise JSONConfigError("Invalid file path or read error", file_path, cause=e)

    if not isinstance(data, dict):
        raise JSONConfigError(
            "JSON root must be an object (dict), got {0}".format(type(data).__name__),
            file_path,
            cause=None,
        )

    return data


class JSONReader:
    """
    Read-only access to a JSON dict by dot-separated path (e.g. 'default.logLevel').
    Works on in-memory data only; no file I/O. Use for settings, config, or any JSON data.
    """

    def __init__(self, config_data: Dict[str, Any]):
        if not isinstance(config_data, dict):
            raise TypeError("config_data must be a dict")
        self.config_data = config_data

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get value by dot-separated path (e.g. 'default.logLevel', 'environments.development').
        """
        try:
            keys = key_path.split(".")
            value = self.config_data
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_section(self, section_path: str) -> Dict[str, Any]:
        """Get entire section as dict (e.g. 'default', 'session')."""
        return self.get(section_path, {})
