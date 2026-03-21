# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests — CLI implement subcommand.

Tests: implement command output paths, suffix stripping, missing spec error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.cli import app
from specweaver.llm.models import LLMResponse

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


def _scaffold(tmp_path: Path) -> Path:
    """Create a minimal project scaffold."""
    (tmp_path / ".specweaver").mkdir(exist_ok=True)
    (tmp_path / "specs").mkdir(exist_ok=True)
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "tests").mkdir(exist_ok=True)
    return tmp_path


def _make_mock_adapter(text: str = "pass\n") -> MagicMock:
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

    @patch("specweaver.cli._helpers._require_llm_adapter")
    def test_output_files_created(
        self, mock_require, tmp_path: Path,
    ) -> None:
        """implement → creates code + test files."""
        project = _scaffold(tmp_path)
        spec = project / "specs" / "greeter_spec.md"
        spec.write_text("# Greeter Spec\n## 1. Purpose\nGreets.\n", encoding="utf-8")

        mock_require.return_value = (
            MagicMock(), _make_mock_adapter("def greet(): pass\n"),
            MagicMock(temperature=0.7),
        )

        result = runner.invoke(
            app, ["implement", str(spec), "--project", str(project)],
        )
        assert result.exit_code == 0
        assert (project / "src" / "greeter.py").exists()
        assert (project / "tests" / "test_greeter.py").exists()

    @patch("specweaver.cli._helpers._require_llm_adapter")
    def test_spec_suffix_stripped(
        self, mock_require, tmp_path: Path,
    ) -> None:
        """'_spec' suffix stripped from output filenames."""
        project = _scaffold(tmp_path)
        spec = project / "specs" / "auth_service_spec.md"
        spec.write_text("# Auth Spec\n## 1. Purpose\nAuth.\n", encoding="utf-8")

        mock_require.return_value = (
            MagicMock(), _make_mock_adapter("pass\n"),
            MagicMock(temperature=0.7),
        )

        result = runner.invoke(
            app, ["implement", str(spec), "--project", str(project)],
        )
        assert result.exit_code == 0
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
            app, ["implement", "nonexistent.md", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
