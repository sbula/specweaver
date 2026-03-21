# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests for pipeline execution — sw run / sw resume.

Exercises the full CLI → parser → runner → handler → state pipeline
with the real StateStore, PipelineRunner, and display backends.
Only the LLM adapter is mocked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all e2e tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


@pytest.fixture()
def project_with_spec(tmp_path: Path) -> tuple[Path, Path]:
    """Create an initialized project with a valid spec file."""
    project_dir = tmp_path / "e2e-pipe-proj"
    project_dir.mkdir()
    result = runner.invoke(app, ["init", "e2e-pipe", "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed: {result.output}"

    spec = project_dir / "specs" / "calculator_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(
        "# Calculator — Component Spec\n\n"
        "> **Status**: DRAFT\n\n---\n\n"
        "## 1. Purpose\n\n"
        "A basic arithmetic calculator module.\n\n---\n\n"
        "## 2. Contract\n\n"
        "```python\n"
        "def add(a: int, b: int) -> int:\n"
        '    """Return the sum of a and b."""\n'
        "```\n\n"
        "### Examples\n\n"
        "```python\n"
        ">>> add(2, 3)\n"
        "5\n"
        ">>> add(-1, 1)\n"
        "0\n"
        "```\n\n---\n\n"
        "## 3. Protocol\n\n"
        "1. Accept two integer arguments `a` and `b`.\n"
        "2. MUST return the sum as an integer.\n"
        "3. The function MUST NOT raise exceptions.\n\n---\n\n"
        "## 4. Policy\n\n"
        "| Error | Behavior |\n|:---|:---|\n"
        "| Invalid type | Raise TypeError |\n"
        "| Overflow | Use Python's arbitrary precision |\n\n---\n\n"
        "## 5. Boundaries\n\n"
        "| Concern | Owned By |\n|:---|:---|\n"
        "| Logging | LogService |\n\n---\n\n"
        "## Done Definition\n\n"
        "- [ ] Unit tests pass\n"
        "- [ ] Coverage >= 70%\n",
        encoding="utf-8",
    )
    return project_dir, spec


# ---------------------------------------------------------------------------
# sw run — full pipeline execution
# ---------------------------------------------------------------------------


class TestRunPipelineE2E:
    """Execute real pipelines through the CLI."""

    def test_run_validate_only_completes(
        self, project_with_spec: tuple[Path, Path], monkeypatch,
    ) -> None:
        """sw run validate_only on a good spec → exit 0 or 1 (rule results)."""
        project_dir, spec = project_with_spec
        monkeypatch.setattr(
            "specweaver.cli.pipelines._STATE_DB_PATH",
            project_dir / ".specweaver" / "pipeline_state.db",
        )

        result = runner.invoke(
            app,
            ["run", "validate_only", str(spec), "--project", str(project_dir)],
        )
        # validate_only runs all spec rules — may pass or fail but shouldn't crash
        assert result.exit_code in (0, 1)
        # Should show rule results (S01, S02, etc.)
        assert "S01" in result.output or "validate" in result.output.lower()

    def test_run_validate_only_json_output(
        self, project_with_spec: tuple[Path, Path], monkeypatch,
    ) -> None:
        """sw run validate_only --json produces NDJSON event output."""
        project_dir, spec = project_with_spec
        monkeypatch.setattr(
            "specweaver.cli.pipelines._STATE_DB_PATH",
            project_dir / ".specweaver" / "pipeline_state.db",
        )

        result = runner.invoke(
            app,
            ["run", "validate_only", str(spec), "--project", str(project_dir), "--json"],
        )
        assert result.exit_code in (0, 1)
        # JSON output should contain event data
        assert "{" in result.output  # at least some JSON

    def test_run_validate_only_verbose(
        self, project_with_spec: tuple[Path, Path], monkeypatch,
    ) -> None:
        """sw run validate_only --verbose produces detailed output."""
        project_dir, spec = project_with_spec
        monkeypatch.setattr(
            "specweaver.cli.pipelines._STATE_DB_PATH",
            project_dir / ".specweaver" / "pipeline_state.db",
        )

        result = runner.invoke(
            app,
            ["run", "validate_only", str(spec), "--project", str(project_dir), "--verbose"],
        )
        assert result.exit_code in (0, 1)

    def test_run_nonexistent_spec_fails(
        self, project_with_spec: tuple[Path, Path], monkeypatch,
    ) -> None:
        """sw run validate_only on missing spec → exit 1."""
        project_dir, _ = project_with_spec
        monkeypatch.setattr(
            "specweaver.cli.pipelines._STATE_DB_PATH",
            project_dir / ".specweaver" / "pipeline_state.db",
        )

        result = runner.invoke(
            app,
            ["run", "validate_only", "nonexistent.md", "--project", str(project_dir)],
        )
        assert result.exit_code == 1

    def test_run_invalid_pipeline_fails(
        self, project_with_spec: tuple[Path, Path], monkeypatch,
    ) -> None:
        """sw run with unknown pipeline → exit 1."""
        project_dir, spec = project_with_spec
        monkeypatch.setattr(
            "specweaver.cli.pipelines._STATE_DB_PATH",
            project_dir / ".specweaver" / "pipeline_state.db",
        )

        result = runner.invoke(
            app,
            ["run", "nonexistent_pipeline_xyz", str(spec), "--project", str(project_dir)],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# sw resume — persistence and resume
# ---------------------------------------------------------------------------


class TestResumePipelineE2E:
    """Resume pipeline operations through the CLI."""

    def test_resume_nonexistent_id(
        self, project_with_spec: tuple[Path, Path], monkeypatch,
    ) -> None:
        """sw resume with garbage ID → exit 1."""
        project_dir, _ = project_with_spec
        monkeypatch.setattr(
            "specweaver.cli.pipelines._STATE_DB_PATH",
            project_dir / ".specweaver" / "pipeline_state.db",
        )

        result = runner.invoke(app, ["resume", "fake-run-id-12345"])
        assert result.exit_code == 1

    def test_resume_no_resumable_runs(
        self, project_with_spec: tuple[Path, Path], monkeypatch,
    ) -> None:
        """sw resume with no parked/failed runs → exit 0 with message."""
        project_dir, _ = project_with_spec
        monkeypatch.setattr(
            "specweaver.cli.pipelines._STATE_DB_PATH",
            project_dir / ".specweaver" / "pipeline_state.db",
        )

        result = runner.invoke(app, ["resume"])
        assert result.exit_code == 0
        assert "no resumable" in result.output.lower()


# ---------------------------------------------------------------------------
# sw pipelines — listing
# ---------------------------------------------------------------------------


class TestPipelinesE2E:

    def test_pipelines_lists_bundled(self) -> None:
        result = runner.invoke(app, ["pipelines"])
        assert result.exit_code == 0
        output = result.output.lower()
        assert "validate" in output or "new_feature" in output or "pipeline" in output

    def test_pipelines_shows_usage_hint(self) -> None:
        result = runner.invoke(app, ["pipelines"])
        assert result.exit_code == 0
        assert "sw run" in result.output.lower()
