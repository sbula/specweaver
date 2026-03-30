# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Centralized SpecWeaver data path resolution.

All SpecWeaver runtime data (SQLite databases, logs) lives under a single
root directory.  By default this is ``~/.specweaver/``, but it can be
overridden via the ``SPECWEAVER_DATA_DIR`` environment variable for
containers, CI, or custom installs.

Usage::

    from specweaver.config.paths import config_db_path, state_db_path

    db = Database(config_db_path())
    store = StateStore(state_db_path())
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def specweaver_root() -> Path:
    """Return the SpecWeaver data root directory.

    Resolution order:
        1. ``SPECWEAVER_DATA_DIR`` env var (containers, CI)
        2. ``~/.specweaver/`` (default)

    An empty env var is treated as unset (falls back to default).
    """
    override = os.environ.get("SPECWEAVER_DATA_DIR", "").strip()
    if override:
        logger.debug("Using SPECWEAVER_DATA_DIR override: %s", override)
        return Path(override)
    return Path.home() / ".specweaver"


def config_db_path() -> Path:
    """Return the path to the configuration database (``specweaver.db``)."""
    return specweaver_root() / "specweaver.db"


def state_db_path() -> Path:
    """Return the path to the pipeline state database (``pipeline_state.db``)."""
    return specweaver_root() / "pipeline_state.db"


def logs_dir() -> Path:
    """Return the path to the logs directory."""
    return specweaver_root() / "logs"
