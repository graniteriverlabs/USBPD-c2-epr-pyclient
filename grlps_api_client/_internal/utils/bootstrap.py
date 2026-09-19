"""
Bootstrap: one-time system init for logging and config.
Returns config_manager, log_manager, and session_logger for the rest of the run.
"""

import logging
import sys
import os
import re
import subprocess
from typing import Tuple, Optional, List, Dict, Any

# Use package-local compat helper.
from . import compat
from utils.log_manager import LogManager
from utils.run_context import stamped_filename
from utils.unified_config_manager import UnifiedConfigManager


def _resolve_project_root_from_file(file_path: str) -> str:
    env_root = os.environ.get("GRLPS_API_PROJECT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    root = os.path.dirname(os.path.dirname(os.path.abspath(file_path)))
    if os.path.basename(root).lower() == "runtime_internal_pyc":
        return os.path.dirname(root)
    return root


def _get_installed_python_versions() -> List[str]:
    """
    Detect Python interpreter versions present on the system (python, python3, py -3, etc.).
    Returns a sorted list of version strings (e.g. ['3.11.0']). Informational only; this project runs on Python 3.x.
    """
    seen = set()
    results = []
    is_win = compat.IS_WINDOWS
    # Commands to try: (executable, args list or None)
    if is_win:
        commands = [
            ("python", None),
            ("python3", None),
            ("py", ["-3"]),
        ]
    else:
        commands = [
            ("python3", None),
            ("python", None),
        ]
    for exe, args in commands:
        cmd = [exe] + (args or []) + ["--version"]
        try:
            out = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
            )
            text = (out or "").strip()
        except (subprocess.CalledProcessError, OSError):
            continue
        except Exception:
            continue  # e.g. TimeoutExpired, missing executable
        # Parse "Python 3.11.0" -> "3.11.0"
        match = re.search(r"Python\s+(\d+\.\d+(?:\.\d+)?)", text)
        if match and match.group(1) not in seen:
            seen.add(match.group(1))
            results.append(match.group(1))
    return sorted(results, key=lambda v: [int(x) for x in v.split(".") if x.isdigit()])


def create_bootstrap_logger() -> logging.Logger:
    """
    Create a temporary console-only logger for the initialization phase.
    Should be closed after session_logger is created.
    """
    logger = logging.getLogger("Bootstrap")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    return logger


def _close_bootstrap_logger(logger: logging.Logger) -> None:
    """Close and clear bootstrap logger handlers."""
    for h in logger.handlers:
        h.close()
    logger.handlers.clear()


def _apply_session_log_overrides_from_grlps_app_common(
    session_config: Dict[str, Any],
    common: Any,
    project_root: str,
) -> Dict[str, Any]:
    """
    Override session log directory / file name from grlps_app_config.json (common).

    End users edit only grlps_app_config.json; logging_config.json can stay as shipped
    defaults. Optional keys in common:

    - sessionLogDirectory: folder (relative to project root or absolute)
    - sessionLogFileName: log file name only
    - sessionLogLevel: e.g. INFO, DEBUG (passed to LogManager)
    - sessionLogPerRun: when true (default) the run stamp is inserted into the
      file name so every run writes its own log instead of appending to one file
    """
    if not isinstance(common, dict):
        common = {}
    cfg = dict(session_config)
    cur = cfg.get("logFilename") or ""
    cur_dir = os.path.dirname(cur) if cur else os.path.join(project_root, "user_interaction", "logs")
    cur_base = os.path.basename(cur) if cur else "api_framework_session.log"

    dname = common.get("sessionLogDirectory")
    fname = common.get("sessionLogFileName")
    lvl = common.get("sessionLogLevel")

    new_dir = cur_dir
    if isinstance(dname, str) and dname.strip():
        new_dir = dname.strip()
        if not os.path.isabs(new_dir):
            new_dir = os.path.normpath(os.path.join(project_root, new_dir))

    new_base = cur_base
    if isinstance(fname, str) and fname.strip():
        new_base = fname.strip()

    # One log file per run: the shared run stamp keeps this run's session log and
    # the launched app's console log next to each other in the same folder.
    if bool(common.get("sessionLogPerRun", True)):
        new_base = stamped_filename(new_base)

    try:
        os.makedirs(new_dir, exist_ok=True)
    except OSError:
        pass
    cfg["logFilename"] = os.path.join(new_dir, new_base)

    if isinstance(lvl, str) and lvl.strip():
        cfg["logLevel"] = lvl.strip().upper()
    return cfg


def initialize_system(
    logging_config_file: Optional[str] = None,
    app_config_file: Optional[str] = None,
) -> Tuple[UnifiedConfigManager, LogManager, logging.Logger]:
    """
    Initialize the framework: load config, create session logger.

    Session log file path and name are taken from grlps_app_config.json (common):
    sessionLogDirectory, sessionLogFileName, sessionLogLevel — so end users only
    need to edit grlps_app_config.json. logging_config.json remains internal defaults.

    Args:
        logging_config_file: Path to logging_config.json. If None or if file does
            not exist, built-in Python defaults are used (suitable for customer
            builds without the JSON file).
        app_config_file: Path to grlps_app_config.json. If None, uses config/grlps_app_config.json.
            File is required; initialization fails if missing or invalid.

    Returns:
        (config_manager, log_manager, session_logger)
        - config_manager: unified config (logging + app config).
        - log_manager: LogManager instance used to create session_logger.
        - session_logger: logger to use for the rest of the run.
    """
    _dir = _resolve_project_root_from_file(__file__)
    if logging_config_file is None:
        logging_config_file = os.path.join(_dir, "config", "logging_config.json")
    if app_config_file is None:
        app_config_file = os.path.join(_dir, "config", "grlps_app_config.json")

    bootstrap = create_bootstrap_logger()
    bootstrap.info("Starting API framework initialization...")
    # Log Python version (running), OS, and Python versions installed on system so user can check both
    py_ver = "Python {0}.{1}.{2}".format(
        sys.version_info[0],
        sys.version_info[1],
        sys.version_info[2],
    )
    os_name = "Windows" if compat.IS_WINDOWS else ("Linux" if compat.IS_LINUX else sys.platform)
    bootstrap.info("Runtime: %s | OS: %s", py_ver, os_name)
    installed = _get_installed_python_versions()
    if installed:
        bootstrap.info("Python versions installed on system: %s", ", ".join(installed))
    else:
        bootstrap.info("Python versions installed on system: (could not detect)")

    try:
        config_manager = UnifiedConfigManager(
            logging_config_file=logging_config_file,
            app_config_file=app_config_file,
            logger=bootstrap,
        )

        session_config = config_manager.get_logging_config_for_app("session")
        session_config = _apply_session_log_overrides_from_grlps_app_common(
            session_config,
            config_manager.get_common(),
            _dir,
        )
        log_manager = LogManager.from_config(session_config)
        session_logger = log_manager.get_logger()

        config_manager.set_logger(session_logger)

        session_logger.info("=" * 60)
        session_logger.info("Runtime: %s | OS: %s", py_ver, os_name)
        if installed:
            session_logger.info("Python versions installed on system: %s", ", ".join(installed))
        session_logger.info("API framework initialized successfully")
        session_logger.info("Session log file: %s", log_manager.log_filename)
        session_logger.info("=" * 60)

        _close_bootstrap_logger(bootstrap)
        return (config_manager, log_manager, session_logger)

    except Exception as e:
        bootstrap.error("Initialization failed: %s", e)
        _close_bootstrap_logger(bootstrap)
        raise
