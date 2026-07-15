# mypy: ignore-errors
from pathlib import Path

import pytest
from pydantic import ValidationError

from specweaver.core.config.database import Database
from specweaver.core.config.settings import SandboxSettings, SpecWeaverSettings
from specweaver.core.config.settings_loader import load_settings
from tests.fixtures.db_utils import register_test_project


class TestSandboxSettingsModel:
    """Bare-model tests for SandboxSettings (INT-US-09 SF-01 T10).

    Loader-level (specweaver.toml -> SandboxSettings) tests land in T11.
    """

    def test_defaults_to_host_mode(self):
        settings = SandboxSettings()
        assert settings.execution_mode == "host"

    def test_accepts_container_mode(self):
        settings = SandboxSettings(execution_mode="container")
        assert settings.execution_mode == "container"

    def test_rejects_invalid_execution_mode(self):
        with pytest.raises(ValidationError):
            SandboxSettings(execution_mode="not-a-real-mode")

    def test_spec_weaver_settings_defaults_sandbox_to_host(self):
        settings = SpecWeaverSettings(llm={"model": "gemini-2.0-flash"})
        assert settings.sandbox.execution_mode == "host"


def test_load_settings_toml_overrides_defaults(tmp_path: Path):
    # Setup mock db and project
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    # Write specweaver.toml with standards best_practice
    toml_path = project_path / "specweaver.toml"
    toml_path.write_text('[standards]\nmode = "best_practice"\n', encoding="utf-8")

    # Load settings
    settings = load_settings(db, "my_project", llm_role="review")

    # Assert
    assert hasattr(settings, "standards")
    assert settings.standards.mode == "best_practice"


def test_load_settings_toml_absent_keeps_defaults(tmp_path: Path):
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    settings = load_settings(db, "my_project", llm_role="review")
    assert hasattr(settings, "standards")
    assert settings.standards.mode == "mimicry"
