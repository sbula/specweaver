# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for config/settings.py — DB-backed settings loading."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temporary DB path."""
    return tmp_path / ".specweaver" / "specweaver.db"


@pytest.fixture()
def db(db_path: Path):
    """Create a fresh Database."""
    from specweaver.config.database import Database

    return Database(db_path)


# ---------------------------------------------------------------------------
# load_settings (DB-backed)
# ---------------------------------------------------------------------------


class TestLoadSettings:
    """Settings loading from the database."""

    def test_load_for_registered_project(self, db, tmp_path: Path):
        from specweaver.config.settings import load_settings

        db.register_project("myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.llm.model == "gemini-2.5-flash"

    def test_load_uses_review_profile_by_default(self, db, tmp_path: Path):
        """load_settings uses the 'review' profile for the LLM settings."""
        from specweaver.config.settings import load_settings

        db.register_project("myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.llm.temperature == pytest.approx(0.3)

    def test_load_with_role_override(self, db, tmp_path: Path):
        """Can load settings for a specific LLM role."""
        from specweaver.config.settings import load_settings

        db.register_project("myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp", llm_role="draft")
        assert settings.llm.temperature == pytest.approx(0.7)

    def test_load_search_role(self, db, tmp_path: Path):
        from specweaver.config.settings import load_settings

        db.register_project("myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp", llm_role="search")
        assert settings.llm.temperature == pytest.approx(0.1)

    def test_load_nonexistent_project_raises(self, db):
        from specweaver.config.settings import load_settings

        with pytest.raises(ValueError, match="not found"):
            load_settings(db, "nonexistent")

    def test_load_nonexistent_role_uses_defaults(self, db, tmp_path: Path):
        """If a role is not linked, fall back to model defaults."""
        from specweaver.config.settings import load_settings

        db.register_project("myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp", llm_role="custom-unknown")
        # Falls back to LLMSettings defaults
        assert settings.llm.model == "gemini-2.5-flash"
        assert settings.llm.temperature == pytest.approx(0.7)

    def test_load_with_custom_profile(self, db, tmp_path: Path):
        """Custom project-specific profile overrides global."""
        from specweaver.config.settings import load_settings

        db.register_project("myapp", str(tmp_path / "proj"))
        custom_id = db.create_llm_profile(
            name="review",
            is_global=False,
            model="gemini-2.5-pro",
            temperature=0.15,
            max_output_tokens=8192,
        )
        db.link_project_profile("myapp", "review", custom_id)
        settings = load_settings(db, "myapp")
        assert settings.llm.model == "gemini-2.5-pro"
        assert settings.llm.temperature == pytest.approx(0.15)
        assert settings.llm.max_output_tokens == 8192


# ---------------------------------------------------------------------------
# API key from env
# ---------------------------------------------------------------------------


class TestAPIKeyFromEnv:
    """API key always comes from environment, never from DB."""

    def test_api_key_from_env(self, db, tmp_path: Path, monkeypatch):
        from specweaver.config.settings import load_settings

        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        db.register_project("myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.llm.api_key == "test-key-123"

    def test_api_key_empty_when_not_set(self, db, tmp_path: Path, monkeypatch):
        from specweaver.config.settings import load_settings

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        db.register_project("myapp", str(tmp_path / "proj"))
        settings = load_settings(db, "myapp")
        assert settings.llm.api_key == ""


# ---------------------------------------------------------------------------
# load_settings_for_active_project
# ---------------------------------------------------------------------------


class TestLoadActiveProject:
    """Loading settings for the currently active project."""

    def test_load_active(self, db, tmp_path: Path):
        from specweaver.config.settings import load_settings_for_active

        db.register_project("myapp", str(tmp_path / "proj"))
        db.set_active_project("myapp")
        settings = load_settings_for_active(db)
        assert settings.llm.model == "gemini-2.5-flash"

    def test_load_no_active_raises(self, db):
        from specweaver.config.settings import load_settings_for_active

        with pytest.raises(ValueError, match=r"[Nn]o active project"):
            load_settings_for_active(db)


# ---------------------------------------------------------------------------
# Legacy migration
# ---------------------------------------------------------------------------


class TestLegacyMigration:
    """Migration from .specweaver/config.yaml to DB."""

    def test_migrate_legacy_config(self, db, tmp_path: Path):
        from specweaver.config.settings import migrate_legacy_config

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
        proj = db.get_project("legacy-app")
        assert proj is not None
        assert proj["root_path"] == str(project_dir)

    def test_migrate_creates_custom_profile(self, db, tmp_path: Path):
        from specweaver.config.settings import load_settings, migrate_legacy_config

        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        config_file = sw_dir / "config.yaml"
        config_file.write_text(
            "llm:\n"
            "  model: gemini-2.5-pro\n"
            "  temperature: 0.5\n",
            encoding="utf-8",
        )

        migrate_legacy_config(db, "legacy-app", str(project_dir))
        settings = load_settings(db, "legacy-app")

        # Should use the imported values for all roles
        assert settings.llm.model == "gemini-2.5-pro"
        assert settings.llm.temperature == pytest.approx(0.5)

    def test_migrate_no_config_file_returns_false(self, db, tmp_path: Path):
        from specweaver.config.settings import migrate_legacy_config

        project_dir = tmp_path / "no-config"
        project_dir.mkdir()
        result = migrate_legacy_config(db, "no-legacy", str(project_dir))
        assert result is False

    def test_migrate_already_registered_raises(self, db, tmp_path: Path):
        from specweaver.config.settings import migrate_legacy_config

        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        sw_dir = project_dir / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text("llm:\n  model: x\n", encoding="utf-8")

        db.register_project("existing", str(project_dir))
        with pytest.raises(ValueError, match="already exists"):
            migrate_legacy_config(db, "existing", str(project_dir))


# ---------------------------------------------------------------------------
# Pydantic model structure
# ---------------------------------------------------------------------------


class TestPydanticModels:
    """SpecWeaverSettings and LLMSettings models."""

    def test_default_settings(self):
        from specweaver.config.settings import SpecWeaverSettings

        s = SpecWeaverSettings()
        assert s.llm.model == "gemini-2.5-flash"
        assert s.llm.temperature == pytest.approx(0.7)
        assert s.llm.api_key == ""

    def test_settings_from_dict(self):
        from specweaver.config.settings import LLMSettings, SpecWeaverSettings

        s = SpecWeaverSettings(
            llm=LLMSettings(model="gemini-2.5-pro", temperature=0.3)
        )
        assert s.llm.model == "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# Legacy migration — edge cases
# ---------------------------------------------------------------------------


class TestLegacyMigrationEdgeCases:
    """Edge cases for migrate_legacy_config."""

    def test_migrate_invalid_yaml(self, db, tmp_path: Path):
        """config.yaml with invalid YAML → project still registered (data=defaults)."""
        from specweaver.config.settings import load_settings, migrate_legacy_config

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
        assert settings.llm.model == "gemini-2.5-flash"

    def test_migrate_non_dict_llm_section(self, db, tmp_path: Path):
        """config.yaml where llm is a string → treated as empty dict."""
        from specweaver.config.settings import load_settings, migrate_legacy_config

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
        assert settings.llm.model == "gemini-2.5-flash"

    def test_migrate_extra_unknown_keys(self, db, tmp_path: Path):
        """config.yaml with extra unknown keys → silently ignored."""
        from specweaver.config.settings import load_settings, migrate_legacy_config

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

