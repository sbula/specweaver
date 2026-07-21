# mypy: ignore-errors
from pathlib import Path

import pytest
from pydantic import ValidationError

from specweaver.core.config.database import Database
from specweaver.core.config.settings import SandboxSettings, SpecWeaverSettings
from specweaver.core.config.settings_loader import load_settings
from tests.fixtures.db_utils import register_test_project


class TestSandboxSettingsModel:
    """Bare-model tests for SandboxSettings (B-EXEC-01).

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

    # --- INT-US-09 T1: enforce_worktree_isolation ---------------------------

    def test_enforce_worktree_isolation_defaults_false(self):
        # Happy path: opt-in policy is off by default (NFR-1 backward compat).
        assert SandboxSettings().enforce_worktree_isolation is False

    def test_enforce_worktree_isolation_accepts_true(self):
        # Happy path: operator can enable it.
        assert SandboxSettings(enforce_worktree_isolation=True).enforce_worktree_isolation is True

    def test_enforce_worktree_isolation_coexists_with_execution_mode(self):
        # Boundary: both sandbox knobs set together (orthogonal, container-free base).
        s = SandboxSettings(execution_mode="host", enforce_worktree_isolation=True)
        assert s.execution_mode == "host"
        assert s.enforce_worktree_isolation is True

    def test_enforce_worktree_isolation_rejects_non_bool(self):
        # Hostile/wrong input: a non-coercible value is rejected.
        with pytest.raises(ValidationError):
            SandboxSettings(enforce_worktree_isolation="not-a-bool")

    def test_spec_weaver_settings_defaults_enforce_isolation_false(self):
        settings = SpecWeaverSettings(llm={"model": "gemini-2.0-flash"})
        assert settings.sandbox.enforce_worktree_isolation is False

    # --- C-EXEC-06 SF-03 T1: enforce_session_isolation + session_allowed_paths ---

    def test_enforce_session_isolation_defaults_false(self):
        # Happy path: per-run isolation is opt-in, off by default (FR-7 / NFR-2).
        assert SandboxSettings().enforce_session_isolation is False

    def test_enforce_session_isolation_accepts_true(self):
        assert SandboxSettings(enforce_session_isolation=True).enforce_session_isolation is True

    def test_session_allowed_paths_defaults_empty(self):
        # Empty means "derive from generation targets" at the composition root.
        assert SandboxSettings().session_allowed_paths == []

    def test_session_allowed_paths_accepts_override_list(self):
        s = SandboxSettings(session_allowed_paths=["src/a.py", "tests/test_a.py"])
        assert s.session_allowed_paths == ["src/a.py", "tests/test_a.py"]

    def test_session_allowed_paths_is_independent_per_instance(self):
        # default_factory guard: no shared-mutable-default leak between instances.
        a = SandboxSettings()
        a.session_allowed_paths.append("src/leak.py")
        assert SandboxSettings().session_allowed_paths == []

    def test_session_knobs_coexist_with_per_step_and_execution_mode(self):
        # Boundary: all three sandbox knobs set together (orthogonal).
        s = SandboxSettings(
            execution_mode="host",
            enforce_worktree_isolation=True,
            enforce_session_isolation=True,
        )
        assert s.enforce_worktree_isolation is True
        assert s.enforce_session_isolation is True

    def test_enforce_session_isolation_rejects_non_bool(self):
        with pytest.raises(ValidationError):
            SandboxSettings(enforce_session_isolation="not-a-bool")

    def test_session_allowed_paths_rejects_non_list(self):
        with pytest.raises(ValidationError):
            SandboxSettings(session_allowed_paths="src/a.py")

    def test_spec_weaver_settings_defaults_session_isolation_false(self):
        settings = SpecWeaverSettings(llm={"model": "gemini-2.0-flash"})
        assert settings.sandbox.enforce_session_isolation is False
        assert settings.sandbox.session_allowed_paths == []


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


def test_load_settings_toml_sandbox_container_mode(tmp_path: Path):
    """B-EXEC-01: [sandbox] TOML section loaded via _load_toml_sandbox."""
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    toml_path = project_path / "specweaver.toml"
    toml_path.write_text('[sandbox]\nexecution_mode = "container"\n', encoding="utf-8")

    settings = load_settings(db, "my_project", llm_role="review")

    assert hasattr(settings, "sandbox")
    assert settings.sandbox.execution_mode == "container"


def test_load_settings_toml_sandbox_enforce_isolation_true(tmp_path: Path):
    """INT-US-09 T1: [sandbox] enforce_worktree_isolation loaded via the TOML splat."""
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    toml_path = project_path / "specweaver.toml"
    toml_path.write_text("[sandbox]\nenforce_worktree_isolation = true\n", encoding="utf-8")

    settings = load_settings(db, "my_project", llm_role="review")

    assert settings.sandbox.enforce_worktree_isolation is True


def test_load_settings_toml_sandbox_enforce_isolation_absent_defaults_false(tmp_path: Path):
    """INT-US-09 T1: absent key keeps the opt-in policy off (NFR-1)."""
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    settings = load_settings(db, "my_project", llm_role="review")

    assert settings.sandbox.enforce_worktree_isolation is False


def test_load_settings_toml_sandbox_session_isolation_true(tmp_path: Path):
    """C-EXEC-06 SF-03 T1: [sandbox] enforce_session_isolation loaded via the TOML splat."""
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    toml_path = project_path / "specweaver.toml"
    toml_path.write_text(
        "[sandbox]\nenforce_session_isolation = true\n"
        'session_allowed_paths = ["src/x.py", "tests/test_x.py"]\n',
        encoding="utf-8",
    )

    settings = load_settings(db, "my_project", llm_role="review")

    assert settings.sandbox.enforce_session_isolation is True
    assert settings.sandbox.session_allowed_paths == ["src/x.py", "tests/test_x.py"]


def test_load_settings_toml_sandbox_session_isolation_absent_defaults_false(tmp_path: Path):
    """C-EXEC-06 SF-03 T1: absent keys keep per-run isolation off + allow-list empty (NFR-2)."""
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    settings = load_settings(db, "my_project", llm_role="review")

    assert settings.sandbox.enforce_session_isolation is False
    assert settings.sandbox.session_allowed_paths == []


def test_load_settings_toml_sandbox_absent_keeps_host_default(tmp_path: Path):
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    settings = load_settings(db, "my_project", llm_role="review")

    assert settings.sandbox.execution_mode == "host"


def test_load_settings_toml_sandbox_malformed_falls_back_to_default(tmp_path: Path, caplog):
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    register_test_project(db, "my_project", str(project_path))

    toml_path = project_path / "specweaver.toml"
    toml_path.write_text("not valid toml [[[", encoding="utf-8")

    with caplog.at_level("ERROR"):
        settings = load_settings(db, "my_project", llm_role="review")

    assert settings.sandbox.execution_mode == "host"
