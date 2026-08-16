# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — CLI implement subcommand.

Tests: implement command output paths, suffix stripping, missing spec error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.fixtures.db_utils import register_test_project, set_test_active_project
from typer.testing import CliRunner

# Force import to test decentralized location (Red Phase)
from specweaver.core.config.settings import SandboxSettings
from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(tmp_path / ".specweaver-test" / "specweaver.db"))
    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.core.config.bootstrap.db_bootstrap.get_db", lambda: db)
    # `_core` does `from … import get_db`, so the name is bound at ITS import time and patching
    # `db_bootstrap.get_db` alone leaves `_core.run_repo_op` on the real database — the target
    # `_core.py:7` names explicitly. Harmless while these tests patched `load_settings` and never
    # asked the repository anything; not harmless now that the command reads the active project.
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)

    # `sw implement` refuses without an active project (INT-US-16 FR-2), since telemetry is
    # attributed per project. These tests are about output PATHS and used to reach their
    # assertions only because they patch `load_settings` — the guard now sits before it. Giving
    # them a real active project is the honest fix; softening the guard to keep them green would
    # be the tail wagging the dog.
    register_test_project(db, "implement_cli_test", str(tmp_path))
    set_test_active_project(db, "implement_cli_test")
    return db


def _scaffold(tmp_path: Path) -> Path:
    """Create a minimal project scaffold."""
    (tmp_path / ".specweaver").mkdir(exist_ok=True)
    (tmp_path / "specs").mkdir(exist_ok=True)
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "tests").mkdir(exist_ok=True)
    return tmp_path


#: The same text is returned for BOTH `generate_code` and `generate_tests`, so it has to be valid
#: as either. It must contain a real `test_` function: since `TECH-017` SF-04 a run that collects
#: nothing fails loud, and `"pass\n"` — the old default — collects nothing. These tests are about
#: output *paths*; before the guard they reached their assertions through a QA step that had
#: silently verified an empty run.
_COLLECTABLE = "def greet():\n    pass\n\n\ndef test_greet_is_callable() -> None:\n    assert greet() is None\n"


def _make_mock_adapter(text: str = _COLLECTABLE) -> MagicMock:
    """Create a mock LLM adapter that returns fixed text."""
    adapter = MagicMock()
    adapter.available.return_value = True
    adapter.generate = AsyncMock(
        return_value=LLMResponse(text=text, model="test-model"),
    )
    return adapter


# ---------------------------------------------------------------------------
# implement — output paths
# ---------------------------------------------------------------------------


class TestImplementOutputPaths:
    """Test implement command output file naming."""

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    @patch("specweaver.core.config.bootstrap.settings_loader.load_settings")
    @patch("specweaver.core.flow.store.FlowRepository.log_artifact_event", new_callable=AsyncMock)
    @patch("specweaver.core.config.database.Database._ensure_schema", create=True)
    def test_output_files_created(
        self,
        mock_ensure_schema,
        mock_log_event,
        mock_load,
        mock_create,
        tmp_path: Path,
    ) -> None:
        """implement → creates code + test files."""
        project = _scaffold(tmp_path)
        spec = project / "specs" / "greeter_spec.md"
        spec.write_text("# Greeter Spec\n## 1. Purpose\nGreets.\n", encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.llm.model = "gemini-2.5-pro"
        mock_settings.sandbox = SandboxSettings()  # real sandbox: isolation off by default

        mock_load.return_value = mock_settings
        mock_create.return_value = (
            mock_settings,
            _make_mock_adapter(),
            MagicMock(temperature=0.7),
        )

        result = runner.invoke(
            app,
            ["implement", str(spec), "--project", str(project)],
        )
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert (project / "src" / "greeter.py").exists()
        assert (project / "tests" / "test_greeter.py").exists()

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    @patch("specweaver.core.config.bootstrap.settings_loader.load_settings")
    @patch("specweaver.core.flow.store.FlowRepository.log_artifact_event", new_callable=AsyncMock)
    @patch("specweaver.core.config.database.Database._ensure_schema", create=True)
    def test_spec_suffix_stripped(
        self,
        mock_ensure_schema,
        mock_log_event,
        mock_load,
        mock_create,
        tmp_path: Path,
    ) -> None:
        """'_spec' suffix stripped from output filenames."""
        project = _scaffold(tmp_path)
        spec = project / "specs" / "auth_service_spec.md"
        spec.write_text("# Auth Spec\n## 1. Purpose\nAuth.\n", encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.llm.model = "gemini-2.5-pro"
        mock_settings.sandbox = SandboxSettings()  # real sandbox: isolation off by default

        mock_load.return_value = mock_settings
        mock_create.return_value = (
            mock_settings,
            _make_mock_adapter(),
            MagicMock(temperature=0.7),
        )

        result = runner.invoke(
            app,
            ["implement", str(spec), "--project", str(project)],
        )
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert (project / "src" / "auth_service.py").exists()
        assert not (project / "src" / "auth_service_spec.py").exists()


# ---------------------------------------------------------------------------
# implement — error paths
# ---------------------------------------------------------------------------


class TestImplementErrors:
    """Test implement error handling."""

    def test_missing_spec_exits_1(self, tmp_path: Path) -> None:
        """implement with nonexistent spec → exit 1."""
        result = runner.invoke(
            app,
            ["implement", "nonexistent.md", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
