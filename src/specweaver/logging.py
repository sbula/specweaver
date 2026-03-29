# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""SpecWeaver logging infrastructure.

Provides structured file-based logging with per-project log files.
Console output stays clean (WARNING+ only); the log file captures
full DEBUG-level detail for post-mortem debugging.

Usage::

    from specweaver.logging import setup_logging

    setup_logging("my-project")  # call once at CLI startup

Then in any module::

    import logging

    logger = logging.getLogger(__name__)
    logger.debug("Processing step %s", step_name)
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SPECWEAVER_ROOT = Path.home() / ".specweaver"
_LOGS_DIR_FALLBACK = _SPECWEAVER_ROOT / "logs"


def _get_logs_dir() -> Path:
    """Return the logs directory, respecting SPECWEAVER_DATA_DIR."""
    from specweaver.config.paths import logs_dir

    return logs_dir()


#: Canonical log format — consistent across all modules and handlers.
#: Example: [2026-03-15 12:04:31] [DEBUG   ] [flow.runner] Starting pipeline run abc123
LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

#: Maximum size per log file before rotation (bytes).
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

#: Number of backup files to keep.
BACKUP_COUNT = 3

#: Valid log level names (upper-case) → logging constants.
LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

#: Sentinel used as fallback project name when no project is active.
_GLOBAL_PROJECT = "_global"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the specified record as a JSON string."""
        log_dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "levelname": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_dict["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_dict)


def get_log_path(project_name: str) -> Path:
    """Return the log file path for a project.

    >>> get_log_path("calculator")
    PosixPath('~/.specweaver/logs/calculator/specweaver.log')
    """
    return _get_logs_dir() / project_name / "specweaver.log"


def setup_logging(
    project_name: str | None = None,
    level: str = "DEBUG",
) -> None:
    """Configure SpecWeaver logging for *project_name*.

    * **File handler**: ``RotatingFileHandler`` at
      ``~/.specweaver/logs/<project>/specweaver.log``.
      Receives all messages at *level* (DEBUG by default).
    * **Console handler**: ``StreamHandler`` on stderr.
      Receives WARNING+ only, so the terminal stays clean.

    This function is **idempotent** — calling it twice with the same
    project name does not add duplicate handlers.

    Args:
        project_name: Name of the active project. Falls back to
            ``_global`` if None.
        level: Minimum log level for the *file* handler.
            Must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    project_name = project_name or _GLOBAL_PROJECT
    level_upper = level.upper()
    file_level = LOG_LEVELS.get(level_upper, logging.DEBUG)

    # Get the root specweaver logger
    root_logger = logging.getLogger("specweaver")

    # Idempotency: if we already configured for this project, skip.
    # We tag the logger with an attribute to detect repeated calls.
    configured_project = getattr(root_logger, "_sw_project", None)
    if configured_project == project_name:
        # Already configured for this project — just update level
        root_logger.setLevel(file_level)
        for handler in root_logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                handler.setLevel(file_level)
        return

    # Clear previous handlers (project change or first call)
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)  # Let handlers filter

    json_formatter = JSONFormatter()

    # --- File handler ---
    log_path = get_log_path(project_name)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # --- Console handler (stderr, WARNING+ only) ---
    console_handler = RichHandler(level=logging.WARNING, rich_tracebacks=True)
    console_formatter = logging.Formatter("%(message)s", datefmt="[%X]")
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Tag the logger so we can detect idempotent re-calls
    root_logger._sw_project = project_name  # type: ignore[attr-defined]

    root_logger.debug(
        "Logging initialised for project '%s' at level %s → %s",
        project_name,
        level_upper,
        log_path,
    )


def teardown_logging() -> None:
    """Remove all SpecWeaver logging handlers.

    Useful in tests to avoid handler accumulation across test cases.
    """
    root_logger = logging.getLogger("specweaver")
    root_logger.handlers.clear()
    if hasattr(root_logger, "_sw_project"):
        del root_logger._sw_project
