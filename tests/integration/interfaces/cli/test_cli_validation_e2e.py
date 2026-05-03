# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — E2E validation pipeline loading via CLI.

Ensures that `sw check` loads custom declarative pipelines through both:
1. Explicit `--pipeline` argument.
2. Implicit translation through active project domain profiles.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

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


class TestValidationeE2E:
    """Test CLI pipeline resolution end-to-end integration."""

    def test_sw_check_with_explicit_pipeline(self, tmp_path, monkeypatch) -> None:
        """`sw check --pipeline custom_pipe` applies the exact custom pipeline."""
        proj_dir = tmp_path / "app"
        proj_dir.mkdir(parents=True)
        monkeypatch.chdir(proj_dir)

        runner.invoke(app, ["init", "app"])

        # Create a custom pipeline inside the project's .specweaver/pipelines directory
        sw_dir = proj_dir / ".specweaver"
        pipes_dir = sw_dir / "pipelines"
        pipes_dir.mkdir(parents=True, exist_ok=True)
        custom_pipe = pipes_dir / "custom_validation.yaml"
        custom_pipe.write_text(
            "name: custom_validation\n"
            "type: validation_pipeline\n"
            "extends: validation_spec_default\n"
            "target: spec\n"
            "remove:\n"
            "  - 's01_one_sentence'\n"
            "override:\n"
            "  s08_ambiguity:\n"
            "    params:\n"
            "      warn_threshold: 0\n"
            "      fail_threshold: 0\n",
            encoding="utf-8",
        )

        spec = proj_dir / "test.md"
        spec.write_text(
            "## 1. Purpose\nShould do something but might fail to do it and could explode.\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "check",
                str(spec.name),
                "--pipeline",
                "custom_validation",
            ],
        )

        # S01 should NOT appear since pipeline disables it.
        # S08 should fail horribly!
        assert "S01" not in result.output, result.output
        assert "FAIL" in result.output, result.output
        assert "S08" in result.output, result.output
        assert result.exit_code != 0, result.output

    def test_sw_check_via_domain_profile_pipeline(self, tmp_path, monkeypatch) -> None:
        """`sw check` automatically uses the pipeline from the active domain profile."""
        proj_dir = tmp_path / "app"
        proj_dir.mkdir(parents=True)
        monkeypatch.chdir(proj_dir)

        res_init = runner.invoke(app, ["init", "app"])
        assert res_init.exit_code == 0, res_init.output

        res_use = runner.invoke(app, ["use", "app"])
        assert res_use.exit_code == 0, res_use.output

        sw_dir = proj_dir / ".specweaver"
        pipes_dir = sw_dir / "pipelines"
        pipes_dir.mkdir(parents=True, exist_ok=True)
        # Profile naming convention requires pipeline to be validation_spec_<name>.yaml
        strict_pipe = pipes_dir / "validation_spec_test.yaml"
        strict_pipe.write_text(
            "name: validation_spec_test\n"
            "type: validation_pipeline\n"
            "extends: validation_spec_default\n"
            "target: spec\n"
            "remove:\n"
            "  - 's01_one_sentence'\n"
            "  - 's08_ambiguity'\n",
            encoding="utf-8",
        )

        # Use CLI to assign the profile by name (from the pipeline filename root)
        result_prof = runner.invoke(app, ["config", "set-profile", "test"])
        assert result_prof.exit_code == 0, result_prof.output

        spec = proj_dir / "test.md"
        spec.write_text("## 1. Purpose\nDoes a thing.\n", encoding="utf-8")

        result = runner.invoke(app, ["check", str(spec.name)])

        # S01 and S08 are false, they should not run at all. S02 or S03 should run.
        assert "S01" not in result.output, result.output
        assert "S08" not in result.output, result.output

        # Verify it still functioned
        assert "Validation" in result.output, result.output
