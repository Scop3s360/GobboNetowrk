"""
CallerOS Settings
=================
Single, strongly-typed configuration source for the entire application.

Configuration is loaded from environment variables and/or a .env file.
All values are validated at load time so the application fails fast
with a clear error rather than crashing later with a cryptic KeyError.

Architectural decision:
    Using Python's dataclasses (rather than a third-party framework such as
    Pydantic) keeps the dependency list minimal and aligns with the guide's
    "simplicity first" principle.  The tradeoff is slightly more validation
    boilerplate, which is acceptable at this scale.

    python-dotenv is the only external dependency added here.  It is a
    lightweight, well-maintained library that handles .env file loading
    without pulling in a large dependency tree.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from core.exceptions import ConfigurationError

def get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        # Package root containing CallerOS.exe
        # E.g. Release/
        # Check if config directory exists around the executable
        # E.g. Release/config/
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "config").is_dir():
            return exe_dir / "config"
        return exe_dir
    return Path(__file__).parent.parent

def get_exe_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent

# Load .env file if present (no error if missing — environment vars win).
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(dotenv_path=get_base_dir() / ".env", override=True)
except ImportError:
    # python-dotenv is optional.  Without it, only real env vars are used.
    pass


# ---------------------------------------------------------------------------
# Supported log levels (validated at load time).
# ---------------------------------------------------------------------------

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass(frozen=True)
class Settings:
    """
    Strongly-typed, immutable application configuration.

    Attributes:
        app_name:    Human-readable application name shown in logs.
        version:     Semantic version string.
        log_level:   Python logging level name (e.g. "INFO").
        log_dir:     Directory where log files are written.
        environment: Deployment environment tag (development / production).
    """

    app_name: str
    version: str
    log_level: str
    log_dir: Path
    environment: str

    # ------------------------------------------------------------------
    # Factory — build from environment variables.
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "Settings":
        """
        Read configuration from environment variables and return a validated
        Settings instance.

        Raises:
            ConfigurationError: If any required value is missing or invalid.
        """
        app_name = _require_env("CALLER_OS_APP_NAME", default="CallerOS")
        version = _require_env("CALLER_OS_VERSION", default="1.0.0")
        log_level = _require_env("CALLER_OS_LOG_LEVEL", default="INFO").upper()
        log_dir_raw = _require_env("CALLER_OS_LOG_DIR", default="logs")
        environment = _require_env("CALLER_OS_ENVIRONMENT", default="development").lower()

        # --- Validate log level ---
        if log_level not in _VALID_LOG_LEVELS:
            raise ConfigurationError(
                f"Invalid log level '{log_level}'. "
                f"Must be one of: {', '.join(sorted(_VALID_LOG_LEVELS))}."
            )

        # --- Validate environment tag ---
        valid_envs = {"development", "production", "test"}
        if environment not in valid_envs:
            raise ConfigurationError(
                f"Invalid environment '{environment}'. "
                f"Must be one of: {', '.join(sorted(valid_envs))}."
            )

        log_dir = Path(log_dir_raw)
        if not log_dir.is_absolute():
            log_dir = (get_exe_dir() / log_dir).resolve()

        return cls(
            app_name=app_name,
            version=version,
            log_level=log_level,
            log_dir=log_dir,
            environment=environment,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_env(key: str, *, default: str | None = None) -> str:
    """
    Return the value of an environment variable.

    Args:
        key:     Environment variable name.
        default: Value to use when the variable is absent.  If None and the
                 variable is absent, a ConfigurationError is raised.

    Raises:
        ConfigurationError: If the variable is absent and no default is given.
    """
    value = os.environ.get(key)
    if value is not None:
        return value
    if default is not None:
        return default
    raise ConfigurationError(
        f"Required environment variable '{key}' is not set."
    )
