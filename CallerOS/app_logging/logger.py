"""
CallerOS Logger
===============
Centralised logging initialisation for the CallerOS application.

Provides a single entry point (setup_logging) that configures the standard
Python logging system with both a console handler and a rotating file handler.

All other modules obtain their logger via:

    import logging
    log = logging.getLogger(__name__)

Architectural decision:
    The standard-library logging module is used directly rather than a
    third-party wrapper.  This keeps the dependency count low and is
    sufficient for the logging requirements of Stage 1.

    Log files are rotated at 5 MB with a maximum of 3 backups so the logs/
    directory does not grow without bound.
"""

import logging
import logging.handlers
from pathlib import Path

from config.settings import Settings

# Module-level sentinel so setup_logging is idempotent.
_logging_initialised: bool = False


def setup_logging(settings: Settings) -> None:
    """
    Initialise application-wide logging.

    Should be called exactly once during application startup, before any
    other module obtains a logger.  Subsequent calls are silently ignored
    (idempotent guard).

    Args:
        settings: Validated application settings.  The log_level and log_dir
                  attributes are used to configure handlers.

    Side effects:
        - Creates ``settings.log_dir`` on disk if it does not exist.
        - Attaches a StreamHandler (console) and a RotatingFileHandler to the
          root logger.
    """
    global _logging_initialised
    if _logging_initialised:
        return

    numeric_level = logging.getLevelName(settings.log_level)
    if not isinstance(numeric_level, int):
        # Fallback — should never happen because settings validates the level.
        numeric_level = logging.INFO

    # Ensure the log directory exists.
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    log_formatter = _build_formatter()
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # --- Console handler ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

    # --- Rotating file handler ---
    log_file = settings.log_dir / "caller_os.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    _logging_initialised = True

    # First log entry — confirms logging is alive.
    logging.getLogger(__name__).info(
        "Logging initialised. level=%s  file=%s",
        settings.log_level,
        log_file,
    )


def reset_logging() -> None:
    """
    Remove all handlers from the root logger and reset the initialisation flag.

    Intended for use in unit tests only so that each test can configure
    logging independently without interference.
    """
    global _logging_initialised
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    _logging_initialised = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_formatter() -> logging.Formatter:
    """Return the standard log record formatter used by all handlers."""
    return logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
