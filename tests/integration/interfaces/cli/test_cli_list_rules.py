# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — sw list-rules CLI command.

Exercises the `sw list-rules` command with default output, --pipeline
filtering, and project-local pipeline display.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database



    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    db = Database(db_path)
    return db


class TestListRulesDefault:
    """Tests for sw list-rules without --pipeline argument."""

    def test_lists_both_default_pipelines(self) -> None:
        """Default output shows both spec and code pipelines."""
        result = runner.invoke(app, ["list-rules"])
        assert result.exit_code == 0
        assert "validation_spec_default" in result.output
        assert "validation_code_default" in result.output

    def test_shows_rule_ids_in_order(self) -> None:
        """Rules are displayed with their IDs in execution order."""
        result = runner.invoke(app, ["list-rules"])
        assert result.exit_code == 0
        # S01 should appear before S07 (execution order)
        s01_pos = result.output.index("S01")
        s07_pos = result.output.index("S07")
        assert s01_pos < s07_pos

    def test_shows_step_names(self) -> None:
        """Rule step names are displayed alongside IDs."""
        result = runner.invoke(app, ["list-rules"])
        assert "s01_one_sentence" in result.output
        assert "s04_dependency_dir" in result.output

    def test_shows_rule_count(self) -> None:
        """Total rule count is displayed for each pipeline."""
        result = runner.invoke(app, ["list-rules"])
        assert "12 rules total" in result.output  # spec pipeline
        assert "rules total" in result.output


class TestListRulesFiltered:
    """Tests for sw list-rules --pipeline."""

    def test_filter_by_spec_pipeline(self) -> None:
        """--pipeline validation_spec_default shows only spec rules."""
        result = runner.invoke(
            app,
            ["list-rules", "--pipeline", "validation_spec_default"],
        )
        assert result.exit_code == 0
        assert "validation_spec_default" in result.output
        assert "S01" in result.output
        assert "C01" not in result.output  # no code rules

    def test_filter_by_code_pipeline(self) -> None:
        """--pipeline validation_code_default shows only code rules."""
        result = runner.invoke(
            app,
            ["list-rules", "--pipeline", "validation_code_default"],
        )
        assert result.exit_code == 0
        assert "validation_code_default" in result.output
        assert "C01" in result.output
        assert "S01" not in result.output  # no spec rules

    def test_filter_by_feature_pipeline(self) -> None:
        """--pipeline validation_spec_feature shows feature rules (no S04)."""
        result = runner.invoke(
            app,
            ["list-rules", "--pipeline", "validation_spec_feature"],
        )
        assert result.exit_code == 0
        assert "validation_spec_feature" in result.output
        assert "S01" in result.output
        assert "S04" not in result.output
        assert "11 rules total" in result.output

    def test_unknown_pipeline_shows_warning(self) -> None:
        """--pipeline with unknown name shows warning."""
        result = runner.invoke(
            app,
            ["list-rules", "--pipeline", "nonexistent_pipeline"],
        )
        assert result.exit_code == 0  # graceful, not a crash
        assert "not found" in result.output.lower()

    def test_filter_by_profile_pipeline(self) -> None:
        """--pipeline validation_spec_web_app shows the web-app profile."""
        result = runner.invoke(
            app,
            ["list-rules", "--pipeline", "validation_spec_web_app"],
        )
        assert result.exit_code == 0
        assert "validation_spec_web_app" in result.output
        assert "S01" in result.output


class TestListRulesProjectLocal:
    """Tests for sw list-rules with project-local pipeline."""

    def test_project_local_pipeline_shown(self, tmp_path: Path) -> None:
        """Project-local pipeline override is picked up by list-rules."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_default.yaml").write_text(
            "name: validation_spec_default\n"
            "version: '1.0'\n"
            "steps:\n"
            "  - name: s01_one_sentence\n"
            "    rule: S01\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["list-rules", "--pipeline", "validation_spec_default", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "1 rules total" in result.output  # only 1 rule in local override
