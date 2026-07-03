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

def get_user_data_dir() -> Path:
    if "PYTEST_CURRENT_TEST" in os.environ:
        test_dir = Path(__file__).parent.parent / "workspaces" / "test_userdata"
        test_dir.mkdir(parents=True, exist_ok=True)
        return test_dir
        
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            path = Path(local_appdata) / "CallerOS"
        else:
            path = Path.home() / "AppData" / "Local" / "CallerOS"
    else:
        path = Path.home() / ".local" / "share" / "CallerOS"
        
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_actual_exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent

def migrate_user_data(old_base: Path, new_base: Path) -> None:
    import shutil
    import logging
    
    # Simple console logger setup if main logging isn't fully ready yet
    m_log = logging.getLogger("CallerOS.migration")
    
    # 1. Migrate .env file
    old_env = old_base / "config" / ".env"
    if not old_env.is_file():
        old_env = old_base / ".env"
        
    new_env = new_base / ".env"
    if old_env.is_file() and not new_env.is_file():
        try:
            new_base.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_env, new_env)
            m_log.info(f"Migration: Copied configuration from {old_env} to {new_env}")
        except Exception as e:
            m_log.error(f"Migration: Failed to copy .env: {e}")
            
    # 2. Migrate database and logs
    old_logs_dir = old_base / "logs"
    new_logs_dir = new_base / "logs"
    if old_logs_dir.is_dir():
        new_logs_dir.mkdir(parents=True, exist_ok=True)
        
        old_db = old_logs_dir / "caller_os_memory.db"
        new_db = new_logs_dir / "caller_os_memory.db"
        if old_db.is_file() and not new_db.is_file():
            try:
                shutil.copy2(old_db, new_db)
                m_log.info(f"Migration: Copied database from {old_db} to {new_db}")
            except Exception as e:
                m_log.error(f"Migration: Failed to copy database: {e}")
                
        old_log = old_logs_dir / "caller_os.log"
        new_log = new_logs_dir / "caller_os.log"
        if old_log.is_file() and not new_log.is_file():
            try:
                shutil.copy2(old_log, new_log)
                m_log.info(f"Migration: Copied log file from {old_log} to {new_log}")
            except Exception as e:
                m_log.error(f"Migration: Failed to copy log: {e}")

    # 3. Migrate workspaces directory
    old_ws_dir = old_base / "workspaces"
    new_ws_dir = new_base / "workspaces"
    if old_ws_dir.is_dir():
        def copy_missing_recursive(src: Path, dst: Path):
            if not src.exists():
                return
            if src.is_file():
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    m_log.info(f"Migration: Copied workspace file {src.name}")
            elif src.is_dir():
                for item in src.iterdir():
                    copy_missing_recursive(item, dst / item.name)
        try:
            copy_missing_recursive(old_ws_dir, new_ws_dir)
        except Exception as e:
            m_log.error(f"Migration: Failed to copy workspaces: {e}")

# Run user data migration immediately on module import
if "PYTEST_CURRENT_TEST" not in os.environ:
    migrate_user_data(get_actual_exe_dir(), get_user_data_dir())

def get_base_dir() -> Path:
    return get_user_data_dir()

def get_exe_dir() -> Path:
    return get_user_data_dir()

# Load .env file if present (no error if missing — environment vars win).
if "PYTEST_CURRENT_TEST" not in os.environ:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(dotenv_path=get_base_dir() / ".env", override=True)


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
        openai_api_key: OpenAI secret API key.
        openai_model:   OpenAI model name.
    """

    app_name: str
    version: str
    log_level: str
    log_dir: Path
    environment: str
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

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

        # Load OpenAI settings from environment
        openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_api_key in ("sk-your-key-here", "your-actual-api-key-here"):
            openai_api_key = ""
        openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

        return cls(
            app_name=app_name,
            version=version,
            log_level=log_level,
            log_dir=log_dir,
            environment=environment,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
        )


_current_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get the single authoritative application settings instance.
    """
    global _current_settings
    if "PYTEST_CURRENT_TEST" in os.environ:
        return Settings.from_env()
    if _current_settings is None:
        _current_settings = Settings.from_env()
    return _current_settings


def reload_settings() -> Settings:
    """
    Reload settings from the environment/.env file.
    """
    global _current_settings
    # Re-trigger dotenv load to pick up file changes
    if "PYTEST_CURRENT_TEST" not in os.environ:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(dotenv_path=get_base_dir() / ".env", override=True)
    _current_settings = Settings.from_env()
    return _current_settings


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
