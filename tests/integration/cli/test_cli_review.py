# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests — sw review / sw draft CLI subcommands.

Covers: review error paths, draft error paths, display formatting.
LLM calls are mocked — these are not e2e tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.cli import app

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


def _init_project(tmp_path: Path, name: str = "rev-proj") -> Path:
    """Helper: init a project and return project dir."""
    project_dir = tmp_path / name
    project_dir.mkdir(exist_ok=True)
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed: {result.output}"
    return project_dir


# ---------------------------------------------------------------------------
# sw review — error paths
# ---------------------------------------------------------------------------


class TestReviewErrors:
    """Test sw review error handling."""

    def test_review_nonexistent_file(self, tmp_path: Path) -> None:
        """sw review with non-existent file fails."""
        _init_project(tmp_path)
        result = runner.invoke(app, ["review", "does_not_exist.md"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_review_nonexistent_spec_for_code(self, tmp_path: Path) -> None:
        """sw review --spec with non-existent spec fails."""
        project_dir = _init_project(tmp_path)
        code = project_dir / "src" / "module.py"
        code.parent.mkdir(parents=True, exist_ok=True)
        code.write_text("def foo(): pass\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "review",
                str(code),
                "--spec",
                "nonexistent_spec.md",
                "--project",
                str(project_dir),
            ],
        )
        # Should fail at the LLM adapter step (no API key) or spec not found
        assert result.exit_code == 1

    @patch("specweaver.cli._helpers._require_llm_adapter")
    def test_review_spec_accepted(
        self,
        mock_llm,
        tmp_path: Path,
    ) -> None:
        """sw review on a spec returns ACCEPTED verdict."""
        from specweaver.llm.models import GenerationConfig

        project_dir = _init_project(tmp_path)
        spec = project_dir / "specs" / "greeter_spec.md"
        spec.write_text(
            "# Greeter — Component Spec\n\n"
            "> **Status**: DRAFT\n\n---\n\n"
            "## 1. Purpose\n\nGreets users.\n",
            encoding="utf-8",
        )

        from specweaver.llm.models import LLMResponse

        mock_adapter = AsyncMock()
        mock_adapter.available.return_value = True

        async def _accepted(*args, **kwargs):
            return LLMResponse(text="VERDICT: ACCEPTED\nLooks good.", model="test-model")

        mock_adapter.generate_with_tools = _accepted
        gen_config = GenerationConfig(model="test-model")
        mock_llm.return_value = (None, mock_adapter, gen_config)

        result = runner.invoke(
            app,
            ["review", str(spec), "--project", str(project_dir)],
        )
        assert result.exit_code == 0
        assert "ACCEPTED" in result.output

    @patch("specweaver.cli._helpers._require_llm_adapter")
    def test_review_spec_denied(
        self,
        mock_llm,
        tmp_path: Path,
    ) -> None:
        """sw review on a spec returns DENIED with findings."""
        from specweaver.llm.models import GenerationConfig

        project_dir = _init_project(tmp_path)
        spec = project_dir / "specs" / "bad_spec.md"
        spec.write_text("Not a real spec.", encoding="utf-8")

        from specweaver.llm.models import LLMResponse

        mock_adapter = AsyncMock()
        mock_adapter.available.return_value = True

        async def _denied(*args, **kwargs):
            return LLMResponse(
                text="VERDICT: DENIED\nMissing sections.\n\n"
                     "### Findings\n"
                     "| Section | Issue | Remedy |\n"
                     "| 2. Contract | No type hints | Add type hints |\n",
                model="test-model",
            )

        mock_adapter.generate_with_tools = _denied
        gen_config = GenerationConfig(model="test-model")
        mock_llm.return_value = (None, mock_adapter, gen_config)

        result = runner.invoke(
            app,
            ["review", str(spec), "--project", str(project_dir)],
        )
        assert result.exit_code == 1
        assert "DENIED" in result.output
        assert "No type hints" in result.output


# ---------------------------------------------------------------------------
# sw draft — error paths
# ---------------------------------------------------------------------------


class TestDraftErrors:
    """Test sw draft error handling."""

    def test_draft_existing_spec_blocked(self, tmp_path: Path) -> None:
        """sw draft refuses to overwrite an existing spec file."""
        project_dir = _init_project(tmp_path)
        existing = project_dir / "specs" / "greeter_spec.md"
        existing.write_text("existing content", encoding="utf-8")

        result = runner.invoke(
            app,
            ["draft", "greeter", "--project", str(project_dir)],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output.lower()

    def test_draft_nonexistent_project(self, tmp_path: Path) -> None:
        """sw draft with bad --project fails."""
        result = runner.invoke(
            app,
            ["draft", "greeter", "--project", str(tmp_path / "nonexistent")],
        )
        assert result.exit_code == 1
