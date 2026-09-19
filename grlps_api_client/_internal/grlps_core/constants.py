"""Shared defaults for GRLPS API client core behavior."""

# Above this many planned tests, progress lines use aggregate stats instead of per-test states=.
DEFAULT_PROGRESS_FULL_STATES_MAX = 32

# Default `common.*` timing values (seconds) when `grlps_app_config.json` omits a key.
# Align with shipped `config/grlps_app_config.json`.
DEFAULT_DELAY_BETWEEN_API_STEPS_SECONDS = 2
DEFAULT_INITIAL_WAIT_SECONDS = 10
DEFAULT_MAX_CONNECTION_ATTEMPTS = 3
DEFAULT_CONNECTION_TIMEOUT_SECONDS = 30
DEFAULT_API_TIMEOUT_SECONDS = 60
DEFAULT_STALL_TIMEOUT_SECONDS = 300
