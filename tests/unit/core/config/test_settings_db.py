# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for config/settings.py — DB-backed settings loading.

LLM models, servers and prices are not loaded here any more: they live in the LLM settings files.
What remains in `LLMSettings` are the run's spend ceilings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest

from tests.fixtures.db_utils import register_test_project, set_test_active_project

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


def _set_stitch_mode(db, project_name, mode):
    from specweaver.workspace.store import WorkspaceRepository

    async def _action():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            await repo.set_stitch_mode(project_name, mode)

    anyio.run(_action)


class TestLoadSettings:
    """Settings loading from the database."""

    def test_load_for_registered_project(self, db, tmp_path: Path):
        from specweaver.core.config.bootstrap.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")

        assert (settings.llm.max_spend_usd, settings.llm.max_tokens_per_run) == (25.0, 20_000_000)

    def test_load_nonexistent_project_raises(self, db):
        from specweaver.core.config.bootstrap.settings_loader import load_settings

        with pytest.raises(ValueError, match="not found"):
            load_settings(db, "nonexistent")


class TestLoadActiveProject:
    """Loading settings for the currently active project."""

    def test_load_active(self, db, tmp_path: Path):
        from specweaver.core.config.bootstrap.settings_loader import load_settings_for_active

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        set_test_active_project(db, "myapp")
        settings = load_settings_for_active(db)

        assert settings.llm.max_spend_usd == 25.0

    def test_load_no_active_raises(self, db):
        from specweaver.core.config.bootstrap.settings_loader import load_settings_for_active

        with pytest.raises(ValueError, match=r"[Nn]o active project"):
            load_settings_for_active(db)


class TestPydanticModels:
    """SpecWeaverSettings and LLMSettings models."""

    def test_the_spend_ceilings_default_to_finite_values(self):
        from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings

        s = SpecWeaverSettings(llm=LLMSettings())

        assert (s.llm.max_spend_usd, s.llm.max_tokens_per_run) == (25.0, 20_000_000)

    def test_a_ceiling_can_be_switched_off(self):
        from specweaver.core.config.settings import LLMSettings

        assert LLMSettings(max_spend_usd=None).max_spend_usd is None


class TestStitchSettingsLoad:
    """Verify stitch settings populate correctly."""

    def test_stitch_api_key_from_env(self, db, monkeypatch, tmp_path: Path):
        from specweaver.core.config.bootstrap.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path))
        _set_stitch_mode(db, "myapp", "auto")

        monkeypatch.setenv("STITCH_API_KEY", "real-key-123")
        settings = load_settings(db, "myapp")

        assert settings.stitch.mode == "auto"
        assert settings.stitch.api_key == "real-key-123"

    def test_stitch_api_key_whitespace_is_handled(self, db, monkeypatch, tmp_path: Path):
        from specweaver.core.config.bootstrap.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path))

        monkeypatch.setenv("STITCH_API_KEY", "   ")
        settings = load_settings(db, "myapp")

        assert settings.stitch.api_key == "   "
