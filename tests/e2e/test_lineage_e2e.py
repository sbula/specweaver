# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests — Artifact Lineage Edge Cases and Tag Survivability.

Ensures that the pipeline CLI invocations correctly interact with physical
files to mint, propagate, and preserve `# sw-artifact` tags across executions,
even when traversing intense LLM reflection loops or fallback pipelines.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.cli import app
from specweaver.llm.models import GenerationConfig, LLMResponse

runner = CliRunner()


def _make_llm(responses: list[str]) -> object:
    mock_llm = AsyncMock()
    mock_llm.available.return_value = True
    mock_llm.provider_name = "mock"
    it = iter(responses)

    async def _generate(
        messages: object,
        config: object = None,
        dispatcher: object = None,
        on_tool_round: object = None,
    ) -> LLMResponse:
        return LLMResponse(text=next(it, "VERDICT: ACCEPTED\nDone."), model="mock")

    mock_llm.generate = _generate
    mock_llm.generate_with_tools = _generate
    return mock_llm



class TestLineageE2EFlow:
    """E2E verification of new_feature artifact tagging."""

    def test_new_feature_outputs_lineage_tags(self, tmp_path: Path, _isolate_env) -> None:
        """Pipeline generation writes physical # sw-artifact tags and pushes lineage to DB."""
        db_path = _isolate_env / "specweaver.db"

        project_dir = tmp_path / "proj_lineage"
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        spec = project_dir / "specs" / "calc_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# sw-artifact: 11111111-2222-3333-4444-555555555555\n# Spec", encoding="utf-8")

        mock_llm = _make_llm([
            "VERDICT: ACCEPTED\nValid spec.",  # review
            "```yaml\nphases: []\n```",       # plan
            "```python\n# sw-artifact: 66666666-2222-3333-4444-555555555555\nx = 1\n```", # generate code
            "```python\n# sw-artifact: 77777777-2222-3333-4444-555555555555\ntest = 1\n```", # generate tests
            "VERDICT: ACCEPTED", # validate code
            "VERDICT: ACCEPTED", # validate tests
        ])

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
            with patch("specweaver.context.hitl_provider.HITLProvider") as mock_hitl_cls:
                mock_hitl = AsyncMock()
                mock_hitl.ask = AsyncMock(return_value="")
                mock_hitl_cls.return_value = mock_hitl

                # Run generating part of the pipeline directly (e.g. generate_code)
                # Since new_feature parks at draft, we just invoke `sw implement` via CLI to prove CLI integration!
                result = runner.invoke(app, ["implement", str(spec), "--project", str(project_dir)])

        assert result.exit_code == 0, f"Code gen failed: {result.output}"

        # Verify physical code exists
        code_file = project_dir / "src" / "calc.py"
        assert code_file.exists(), "Code file was not created"

        # Verify DB got the event
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT artifact_id, parent_id, event_type FROM artifact_events WHERE event_type='generated_code'").fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "11111111-2222-3333-4444-555555555555"  # parent_id was correctly pulled from the spec tag
        conn.close()


# ===========================================================================
# Edge Case 18: Legacy Pre-Tag Compatibility
# ===========================================================================

class TestLegacyE2ECompatibility:
    """Validate legacy untagged structures don't break the CLI."""

    def test_legacy_validate_only_graceful(self, tmp_path: Path, _isolate_env) -> None:
        """Validate an old project that has no `# sw-artifact:` tags whatsoever."""

        project_dir = tmp_path / "proj_legacy"
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        # Write untagged raw spec
        spec = project_dir / "specs" / "old_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Old Spec\nNo UUID here.", encoding="utf-8")

        # We just need to ensure the pipeline runs validation without crashing parsing tags
        result = runner.invoke(app, ["run", "validate_only", str(spec), "--project", str(project_dir)])

        # Since the spec is invalid (doesn't follow rules), it exits with 1, but NOT a python traceback
        assert result.exit_code in (0, 1)
        assert "Traceback" not in result.output, "Failed gracefully with legacy untagged file"


# ===========================================================================
# Edge Case 19: AST Fix Tag Survivability
# ===========================================================================

class TestASTFixSurvivability:
    """Ensures LLM reflection loops cleanly preserve physics tags."""

    def test_lint_fix_retains_tag(self, tmp_path: Path, _isolate_env) -> None:
        """Run `sw run lint_fix-code`. Prove tag is retained in source code."""
        db_path = _isolate_env / "specweaver.db"

        project_dir = tmp_path / "proj_lint"
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        spec = project_dir / "specs" / "foo_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Spec", encoding="utf-8")

        src_dir = project_dir / "src"
        src_dir.mkdir(exist_ok=True)
        code = src_dir / "foo.py"
        code.write_text("# sw-artifact: 99999999-2222-3333-4444-555555555555\ny = x\n", encoding="utf-8")

        # LLM simulating a successful fix that obeys the prompt instruction to keep the tag
        mock_llm = _make_llm([
            "```python\n# sw-artifact: 99999999-2222-3333-4444-555555555555\n# clean code\n```"
        ])

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))

            pipe_def = project_dir / "my_lint.yaml"
            pipe_def.write_text("name: my_lint\nsteps:\n  - name: lint\n    action: lint_fix\n    target: code\n", encoding="utf-8")
            result = runner.invoke(app, ["run", str(pipe_def), str(spec), "--project", str(project_dir)])

        assert result.exit_code == 0, f"Lint fix failed: {result.output}"

        # Verify tag survived in physical file
        assert "99999999-2222-3333-4444-555555555555" in code.read_text(encoding="utf-8")

        # Verify db logged lint_fixed
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT artifact_id, event_type FROM artifact_events WHERE event_type='lint_fixed'").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "99999999-2222-3333-4444-555555555555"
        conn.close()
