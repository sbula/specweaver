# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for config/settings.py — DB-backed settings loading.

LLM models, servers, prices and run limits are not loaded here: they live in the LLM settings files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temporary DB path."""
    return tmp_path / ".specweaver" / "specweaver.db"


@pytest.fixture()
def db(db_path: Path):
    """Create a fresh Database."""
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(db_path))
    return Database(db_path)


class TestLoadSettings:
    """Settings loading from the database."""

    def test_load_for_registered_project(self, db, tmp_path: Path):
        from specweaver.core.config.bootstrap.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")

        assert not hasattr(settings, "llm")
        assert not hasattr(settings, "stitch")

    def test_load_nonexistent_project_raises(self, db):
        from specweaver.core.config.bootstrap.settings_loader import load_settings

        with pytest.raises(ValueError, match="not found"):
            load_settings(db, "nonexistent")
