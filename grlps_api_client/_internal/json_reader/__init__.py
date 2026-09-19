"""
JSON config reader package: load JSON files and access by dot-notation path.
All JSON file errors (not found, invalid JSON, encoding, permission, etc.) are
raised as JSONConfigError for consistent handling in config managers.
"""

from .reader import JSONConfigError, JSONReader, load_json_file

__all__ = [
    "JSONConfigError",
    "JSONReader",
    "load_json_file",
]
