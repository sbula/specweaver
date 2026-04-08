# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

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

from typer.testing import CliRunner

from specweaver.cli.main import app
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
        spec.write_text(
            "# sw-artifact: 11111111-2222-3333-4444-555555555555\n# Spec", encoding="utf-8"
        )

        mock_llm = _make_llm(
            [
                "VERDICT: ACCEPTED\nValid spec.",  # review
                "```yaml\nphases: []\n```",  # plan
                "```python\n# sw-artifact: 66666666-2222-3333-4444-555555555555\nx = 1\n```",  # generate code
                "```python\n# sw-artifact: 77777777-2222-3333-4444-555555555555\ntest = 1\n```",  # generate tests
                "VERDICT: ACCEPTED",  # validate code
                "VERDICT: ACCEPTED",  # validate tests
            ]
        )

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

        # Verify DB got the event with correct model_id
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT artifact_id, parent_id, event_type, model_id FROM artifact_events WHERE event_type='generated_code'"
        ).fetchall()
        assert len(rows) == 1
        assert (
            rows[0][1] == "11111111-2222-3333-4444-555555555555"
        )  # parent_id was correctly pulled from the spec tag
        assert (
            rows[0][3] == "gemini-3-flash-preview"
        )  # model_id properly flowed from context through flow layers to DB

        test_rows = conn.execute(
            "SELECT model_id FROM artifact_events WHERE event_type='generated_tests'"
        ).fetchall()
        if test_rows:
            assert test_rows[0][0] == "gemini-3-flash-preview"

        conn.close()

    def test_draft_spec_injects_tag(self, tmp_path: Path, _isolate_env) -> None:
        """sw draft creates a tag physically and logs the drafted_spec event."""
        db_path = _isolate_env / "specweaver.db"

        project_dir = tmp_path / "proj_lineage_draft"
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        mock_llm = _make_llm(
            [
                "# Some Component\nGenerated content",
            ]
        )

        from specweaver.config.settings import LLMSettings, SpecWeaverSettings

        mock_settings = SpecWeaverSettings(llm=LLMSettings(model="mock"))

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (mock_settings, mock_llm, GenerationConfig(model="mock"))
            with patch("specweaver.context.hitl_provider.HITLProvider") as mock_hitl_cls:
                mock_hitl = AsyncMock()
                mock_hitl.ask = AsyncMock(return_value="")
                mock_hitl_cls.return_value = mock_hitl

                result = runner.invoke(app, ["draft", "feature_x", "--project", str(project_dir)])

        assert result.exit_code == 0, f"Draft failed: {result.output}"

        spec_file = project_dir / "specs" / "feature_x_spec.md"
        assert spec_file.exists()

        content = spec_file.read_text(encoding="utf-8")
        assert "<!-- sw-artifact: " in content, "Physical tag missing from draft output"

        # UUID is physically injected, let's pull it
        import re

        match = re.search(r"<!-- sw-artifact:\s*([a-f0-9-]+)\s*-->", content)
        assert match is not None
        spec_uuid = match.group(1)

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT artifact_id, event_type, model_id FROM artifact_events WHERE event_type='drafted_spec'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == spec_uuid
        assert rows[0][2] == "mock"  # model extracted from context.config.llm.model
        conn.close()

    def test_plan_spec_retains_tag(self, tmp_path: Path, _isolate_env) -> None:
        """PipelineRunner picks up parent uuid and logs generated_plan."""
        db_path = _isolate_env / "specweaver.db"

        project_dir = tmp_path / "proj_lineage_plan"
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        spec = project_dir / "specs" / "old_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text(
            "<!-- sw-artifact: 55555555-4444-3333-2222-111111111111 -->\n# Old Spec",
            encoding="utf-8",
        )

        mock_llm = _make_llm(
            [
                """{
                "spec_path": "old_spec.md",
                "spec_name": "Old Spec",
                "spec_hash": "hash",
                "timestamp": "2026-01-01T00:00:00Z",
                "file_layout": [],
                "architecture": null,
                "tech_stack": [],
                "constraints": [],
                "tasks": [],
                "test_expectations": [],
                "reasoning": "mock plan",
                "confidence": 100
            }"""
            ]
        )

        import asyncio

        from specweaver.config.database import Database
        from specweaver.config.settings import LLMSettings, SpecWeaverSettings
        from specweaver.flow._base import RunContext
        from specweaver.flow.models import PipelineDefinition, StepAction, StepTarget
        from specweaver.flow.runner import PipelineRunner

        pipeline = PipelineDefinition.create_single_step(
            name="plan_spec",
            action=StepAction.PLAN,
            target=StepTarget.SPEC,
        )
        context = RunContext(
            project_path=project_dir,
            spec_path=spec,
            llm=mock_llm,
            config=SpecWeaverSettings(llm=LLMSettings(model="mock")),
            db=Database(db_path),
        )

        pipe_runner = PipelineRunner(pipeline, context)
        asyncio.run(pipe_runner.run())

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT artifact_id, parent_id, event_type, model_id FROM artifact_events WHERE event_type='generated_plan'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "55555555-4444-3333-2222-111111111111"
        assert rows[0][3] == "mock"
        conn.close()

    def test_sw_check_lineage_flag_detects_orphans(self, tmp_path: Path, _isolate_env) -> None:
        """The sw check --lineage command returns exit code 1 if orphans are found."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)

        # Create an orphan file
        orphan = src_dir / "orphan.py"
        orphan.write_text("print('hello')", encoding="utf-8")

        # Ensure standard check doesn't care
        runner.invoke(app, ["check", "--project", str(project_dir)])
        # Standard check might fail due to empty project/no specs, but shouldn't fail due to lineage
        # We just want to ensure --lineage triggers the lineage scan specifically

        # Now test with --lineage flag
        result = runner.invoke(app, ["check", "--project", str(project_dir), "--lineage"])

        assert result.exit_code == 1, (
            f"Expected validation failure due to orphaned files, got {result.exit_code}"
        )
        assert "Lineage Tracking Error" in result.output
        assert "orphan.py" in result.output
        assert "Missing '# sw-artifact:' tags" in result.output


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
        result = runner.invoke(
            app, ["run", "validate_only", str(spec), "--project", str(project_dir)]
        )

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
        code.write_text(
            "# sw-artifact: 99999999-2222-3333-4444-555555555555\ny = x\n", encoding="utf-8"
        )

        # LLM simulating a successful fix that obeys the prompt instruction to keep the tag
        mock_llm = _make_llm(
            ["```python\n# sw-artifact: 99999999-2222-3333-4444-555555555555\n# clean code\n```"]
        )

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))

            pipe_def = project_dir / "my_lint.yaml"
            pipe_def.write_text(
                "name: my_lint\nsteps:\n  - name: lint\n    action: lint_fix\n    target: code\n",
                encoding="utf-8",
            )
            result = runner.invoke(
                app, ["run", str(pipe_def), str(spec), "--project", str(project_dir)]
            )

        assert result.exit_code == 0, f"Lint fix failed: {result.output}"

        # Verify tag survived in physical file
        assert "99999999-2222-3333-4444-555555555555" in code.read_text(encoding="utf-8")

        # Verify db logged lint_fixed with correct model_id
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT artifact_id, event_type, model_id FROM artifact_events WHERE event_type='lint_fixed'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "99999999-2222-3333-4444-555555555555"
        assert (
            rows[0][2] == "gemini-3-flash-preview"
        )  # Ensure pipeline fallback/resolved model hit DB
        conn.close()
