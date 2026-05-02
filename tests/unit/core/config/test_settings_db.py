# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for config/settings.py — DB-backed settings loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.fixtures.db_utils import get_test_project, register_test_project, set_test_active_project

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temporary DB path."""
    return tmp_path / ".specweaver" / "specweaver.db"


@pytest.fixture()
def db(db_path: Path):
    """Create a fresh Database."""
    from specweaver.core.config.database import Database
    from specweaver.interfaces.cli._db_utils import bootstrap_database

    bootstrap_database(str(db_path))
    return Database(db_path)


import anyio


def _create_llm_profile(
    db, name, is_global, model, provider="gemini", temperature=0.7, max_output_tokens=8192
):
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _action():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            profile_id = await repo.create_llm_profile(
                name=name,
                is_global=is_global,
                provider=provider,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format="text",
            )
            return profile_id

    return anyio.run(_action)


def _link_project_profile(db, project_name, role_key, profile_id):
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _action():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.link_project_profile(project_name, role_key, profile_id)

    anyio.run(_action)


def _set_stitch_mode(db, project_name, mode):
    from specweaver.workspace.store import WorkspaceRepository

    async def _action():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            await repo.set_stitch_mode(project_name, mode)

    anyio.run(_action)


# ---------------------------------------------------------------------------
# load_settings (DB-backed)
# ---------------------------------------------------------------------------


class TestLoadSettings:
    """Settings loading from the database."""

    def test_load_for_registered_project(self, db, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.llm.model == "gemini-2.5-flash"
        assert settings.llm.provider == "gemini"

    def test_load_uses_review_profile_by_default(self, db, tmp_path: Path):
        """load_settings uses the 'review' profile for the LLM settings."""
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.llm.temperature == pytest.approx(0.0)

    def test_load_with_role_override(self, db, tmp_path: Path):
        """Can load settings for a specific LLM role."""
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp", llm_role="implement")
        assert settings.llm.temperature == pytest.approx(0.2)

    def test_load_search_role(self, db, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp", llm_role="search")
        assert settings.llm.temperature == pytest.approx(0.7)

    def test_load_nonexistent_project_raises(self, db):
        from specweaver.interfaces.cli.settings_loader import load_settings

        with pytest.raises(ValueError, match="not found"):
            load_settings(db, "nonexistent")

    def test_load_nonexistent_role_uses_defaults(self, db, tmp_path: Path):
        """If a role is not linked, fall back to model defaults."""
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp", llm_role="custom-unknown")
        # Falls back to LLMSettings defaults via system-default
        assert settings.llm.model == "gemini-2.5-pro"
        assert settings.llm.temperature == pytest.approx(0.7)

    def test_load_with_custom_profile(self, db, tmp_path: Path):
        """Custom project-specific profile overrides global."""
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        custom_id = _create_llm_profile(
            db=db,
            name="review",
            is_global=False,
            model="gemini-2.5-pro",
            temperature=0.15,
            max_output_tokens=8192,
        )
        _link_project_profile(db, "myapp", "review", custom_id)
        settings = load_settings(db, "myapp")
        assert settings.llm.model == "gemini-2.5-pro"
        assert settings.llm.provider == "gemini"
        assert settings.llm.temperature == pytest.approx(0.15)
        assert settings.llm.max_output_tokens == 8192


# ---------------------------------------------------------------------------
# API key from env
# ---------------------------------------------------------------------------


class TestAPIKeyFromEnv:
    """API key always comes from environment, never from DB."""

    def test_api_key_from_env(self, db, tmp_path: Path, monkeypatch):
        from specweaver.interfaces.cli.settings_loader import load_settings

        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.llm.api_key == "test-key-123"

    def test_api_key_empty_when_not_set(self, db, tmp_path: Path, monkeypatch):
        from specweaver.interfaces.cli.settings_loader import load_settings

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.llm.api_key == ""

    def test_default_stitch_mode_is_off(self, db, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.stitch.mode == "off"

    def test_stitch_api_key_from_env(self, db, tmp_path: Path, monkeypatch):
        from specweaver.interfaces.cli.settings_loader import load_settings

        monkeypatch.setenv("STITCH_API_KEY", "test-stitch-key-123")
        register_test_project(db, "myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.stitch.api_key == "test-stitch-key-123"

    def test_api_key_from_custom_provider(self, db, tmp_path: Path, monkeypatch):
        """If provider is anthropic, the anthropic api key is loaded."""
        from specweaver.interfaces.cli.settings_loader import load_settings

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic-123")
        register_test_project(db, "myapp", str(tmp_path / "proj"))

        # Integration test (Story 5)
        custom_id = _create_llm_profile(
            db=db, name="review", is_global=False, model="claude-3-opus", provider="anthropic"
        )
        _link_project_profile(db, "myapp", "review", custom_id)

        settings = load_settings(db, "myapp")
        assert settings.llm.provider == "anthropic"
        assert settings.llm.api_key == "sk-anthropic-123"

    def test_api_key_empty_when_custom_provider_key_missing(self, db, tmp_path: Path, monkeypatch):
        """If provider is anthropic but ANTHROPIC_API_KEY is missing, api_key is empty string."""
        from specweaver.interfaces.cli.settings_loader import load_settings

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        register_test_project(db, "myapp", str(tmp_path / "proj"))

        custom_id = _create_llm_profile(
            db=db, name="review", is_global=False, model="claude-3-opus", provider="anthropic"
        )
        _link_project_profile(db, "myapp", "review", custom_id)

        settings = load_settings(db, "myapp")
        assert settings.llm.api_key == ""


# ---------------------------------------------------------------------------
# load_settings_for_active_project
# ---------------------------------------------------------------------------


class TestLoadActiveProject:
    """Loading settings for the currently active project."""

    def test_load_active(self, db, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import load_settings_for_active

        register_test_project(db, "myapp", str(tmp_path / "proj"))
        set_test_active_project(db, "myapp")
        settings = load_settings_for_active(db)
        assert settings.llm.model == "gemini-2.5-flash"

    def test_load_no_active_raises(self, db):
        from specweaver.interfaces.cli.settings_loader import load_settings_for_active

        with pytest.raises(ValueError, match=r"[Nn]o active project"):
            load_settings_for_active(db)


# ---------------------------------------------------------------------------
# Legacy migration
# ---------------------------------------------------------------------------


class TestLegacyMigration:
    """Migration from .specweaver/config.yaml to DB."""

    def test_migrate_legacy_config(self, db, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import migrate_legacy_config

        # Create a legacy config file
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        config_file = sw_dir / "config.yaml"
        config_file.write_text(
            "llm:\n"
            "  model: gemini-2.5-pro\n"
            "  temperature: 0.5\n"
            "  max_output_tokens: 2048\n"
            "  response_format: json\n",
            encoding="utf-8",
        )

        result = migrate_legacy_config(db, "legacy-app", str(project_dir))
        assert result is True

        # Verify project registered
        proj = get_test_project(db, "legacy-app")
        assert proj is not None
        assert proj["root_path"] == str(project_dir)

    def test_migrate_creates_custom_profile(self, db, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import load_settings, migrate_legacy_config

        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        config_file = sw_dir / "config.yaml"
        config_file.write_text(
            "llm:\n  model: gemini-2.5-pro\n  temperature: 0.5\n",
            encoding="utf-8",
        )

        migrate_legacy_config(db, "legacy-app", str(project_dir))
        settings = load_settings(db, "legacy-app")

        # Should use the imported values for all roles
        assert settings.llm.model == "gemini-2.5-pro"
        assert settings.llm.temperature == pytest.approx(0.5)

    def test_migrate_maps_custom_provider(self, db, tmp_path: Path):
        """(Story 4) Verify custom provider from yaml is mapped properly."""
        from specweaver.interfaces.cli.settings_loader import load_settings, migrate_legacy_config

        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        config_file = sw_dir / "config.yaml"
        config_file.write_text(
            "llm:\n  model: gpt-4o\n  provider: openai\n",
            encoding="utf-8",
        )

        migrate_legacy_config(db, "legacy-app", str(project_dir))
        settings = load_settings(db, "legacy-app")

        assert settings.llm.provider == "openai"
        assert settings.llm.model == "gpt-4o"

    def test_migrate_no_config_file_returns_false(self, db, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import migrate_legacy_config

        project_dir = tmp_path / "no-config"
        project_dir.mkdir()
        result = migrate_legacy_config(db, "no-legacy", str(project_dir))
        assert result is False

    def test_migrate_already_registered_raises(self, db, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import migrate_legacy_config

        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text("llm:\n  model: x\n", encoding="utf-8")

        register_test_project(db, "existing", str(project_dir))
        with pytest.raises(ValueError, match="already exists"):
            migrate_legacy_config(db, "existing", str(project_dir))


# ---------------------------------------------------------------------------
# Pydantic model structure
# ---------------------------------------------------------------------------


class TestPydanticModels:
    """SpecWeaverSettings and LLMSettings models."""

    def test_default_settings(self):
        from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings

        s = SpecWeaverSettings(llm=LLMSettings(model="gemini-3-flash-preview", provider="gemini"))
        assert s.llm.model == "gemini-3-flash-preview"
        assert s.llm.provider == "gemini"
        assert s.llm.temperature == pytest.approx(0.7)
        assert s.llm.api_key == ""

    def test_settings_from_dict(self):
        from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings

        s = SpecWeaverSettings(
            llm=LLMSettings(model="gemini-2.5-pro", temperature=0.3, provider="gemini")
        )
        assert s.llm.model == "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# Legacy migration — edge cases
# ---------------------------------------------------------------------------


class TestLegacyMigrationEdgeCases:
    """Edge cases for migrate_legacy_config."""

    def test_migrate_invalid_yaml(self, db, tmp_path: Path):
        """config.yaml with invalid YAML → project still registered (data=defaults)."""
        from specweaver.interfaces.cli.settings_loader import load_settings, migrate_legacy_config

        project_dir = tmp_path / "bad-yaml"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text(
            "this is {{{ not: valid yaml ;;;",
            encoding="utf-8",
        )
        result = migrate_legacy_config(db, "bad-yaml", str(project_dir))
        assert result is True
        # Project is registered, with default LLM settings
        settings = load_settings(db, "bad-yaml")
        assert settings.llm.model == "gemini-2.5-pro"

    def test_migrate_non_dict_llm_section(self, db, tmp_path: Path):
        """config.yaml where llm is a string → treated as empty dict."""
        from specweaver.interfaces.cli.settings_loader import load_settings, migrate_legacy_config

        project_dir = tmp_path / "string-llm"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text(
            "llm: 'invalid'\n",
            encoding="utf-8",
        )
        result = migrate_legacy_config(db, "string-llm", str(project_dir))
        assert result is True
        settings = load_settings(db, "string-llm")
        assert settings.llm.model == "gemini-2.5-pro"

    def test_migrate_extra_unknown_keys(self, db, tmp_path: Path):
        """config.yaml with extra unknown keys → silently ignored."""
        from specweaver.interfaces.cli.settings_loader import load_settings, migrate_legacy_config

        project_dir = tmp_path / "extra-keys"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text(
            "llm:\n  model: gemini-2.5-pro\n  temperature: 0.4\n"
            "unknown_section:\n  foo: bar\n"
            "extra_list:\n  - one\n  - two\n",
            encoding="utf-8",
        )
        result = migrate_legacy_config(db, "extra-keys", str(project_dir))
        assert result is True
        settings = load_settings(db, "extra-keys")
        assert settings.llm.model == "gemini-2.5-pro"
        assert settings.llm.temperature == pytest.approx(0.4)


class TestStitchSettingsLoad:
    """Verify stitch settings populate correctly."""

    def test_stitch_api_key_from_env(self, db, monkeypatch, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path))
        _set_stitch_mode(db, "myapp", "auto")

        monkeypatch.setenv("STITCH_API_KEY", "real-key-123")
        settings = load_settings(db, "myapp")

        assert settings.stitch.mode == "auto"
        assert settings.stitch.api_key == "real-key-123"

    def test_stitch_api_key_whitespace_is_handled(self, db, monkeypatch, tmp_path: Path):
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "myapp", str(tmp_path))

        monkeypatch.setenv("STITCH_API_KEY", "   ")
        settings = load_settings(db, "myapp")

        assert settings.stitch.api_key == "   "


# ---------------------------------------------------------------------------
# System-default profile missing (gap #4)
# ---------------------------------------------------------------------------


class TestLoadSettingsNoSystemDefault:
    """load_settings behaviour when system-default profile is missing."""

    def test_load_raises_when_system_default_missing(self, db, tmp_path: Path):
        """If both role profile and system-default are absent → ValueError."""
        from specweaver.interfaces.cli.settings_loader import load_settings

        register_test_project(db, "orphan", str(tmp_path / "orphan"))

        # Delete ALL profiles so no fallback exists (links first to avoid FK)
        with db.connect() as conn:
            conn.execute("DELETE FROM project_llm_links")
            conn.execute("DELETE FROM llm_profiles")

        with pytest.raises(ValueError, match=r"[Ss]ystem default"):
            load_settings(db, "orphan", llm_role="custom-unlinked")


# ---------------------------------------------------------------------------
# migrate_legacy_config — system-default missing (gap #9)
# ---------------------------------------------------------------------------


class TestMigrateLegacyNoSystemDefault:
    """migrate_legacy_config when system-default profile is absent."""

    def test_migrate_raises_when_system_default_missing(self, db, tmp_path: Path):
        """Migration needs system-default for fallback model → ValueError."""
        from specweaver.interfaces.cli.settings_loader import migrate_legacy_config

        # Delete ALL profiles so system-default is gone
        with db.connect() as conn:
            conn.execute("DELETE FROM llm_profiles")

        # Create a project with a legacy config
        project_dir = tmp_path / "legacy"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text("llm:\n  temperature: 0.5\n", encoding="utf-8")

        with pytest.raises(ValueError, match="system-default"):
            migrate_legacy_config(db, "legacy", str(project_dir))


# ---------------------------------------------------------------------------
# migrate_legacy_config — model fallback from system-default (gap #11)
# ---------------------------------------------------------------------------


class TestMigrateLegacyModelFallback:
    """migrate_legacy_config uses system-default model when YAML has no model key."""

    def test_migrate_without_model_uses_system_default(self, db, tmp_path: Path):
        """YAML without 'model' key → falls back to system-default profile model."""
        from specweaver.interfaces.cli.settings_loader import load_settings, migrate_legacy_config

        project_dir = tmp_path / "no-model"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text(
            "llm:\n  temperature: 0.4\n",
            encoding="utf-8",
        )

        result = migrate_legacy_config(db, "no-model", str(project_dir))
        assert result is True

        settings = load_settings(db, "no-model")
        # Model should come from system-default profile
        assert settings.llm.model == "gemini-2.5-pro"
        assert settings.llm.temperature == pytest.approx(0.4)
