# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — sw review / sw draft CLI subcommands.

Covers: review error paths, draft error paths, display formatting.
LLM calls are mocked — these are not e2e tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.database import Database
    from specweaver.core.config.db_bootstrap import bootstrap_database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    db = Database(db_path)
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

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    def test_review_spec_accepted(
        self,
        mock_llm,
        tmp_path: Path,
    ) -> None:
        """sw review on a spec returns ACCEPTED verdict."""
        from specweaver.infrastructure.llm.models import GenerationConfig

        project_dir = _init_project(tmp_path)
        spec = project_dir / "specs" / "greeter_spec.md"
        spec.write_text(
            "# Greeter — Component Spec\n\n"
            "> **Status**: DRAFT\n\n---\n\n"
            "## 1. Purpose\n\nGreets users.\n",
            encoding="utf-8",
        )

        from specweaver.infrastructure.llm.models import LLMResponse

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

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    def test_review_spec_denied(
        self,
        mock_llm,
        tmp_path: Path,
    ) -> None:
        """sw review on a spec returns DENIED with findings."""
        from specweaver.infrastructure.llm.models import GenerationConfig

        project_dir = _init_project(tmp_path)
        spec = project_dir / "specs" / "bad_spec.md"
        spec.write_text("Not a real spec.", encoding="utf-8")

        from specweaver.infrastructure.llm.models import LLMResponse

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


# ---------------------------------------------------------------------------
# INT-US-02 SF-01: draft -> validate -> review inline chain + report
# ---------------------------------------------------------------------------


def _rec(name: str, status, output: dict):
    from types import SimpleNamespace

    return SimpleNamespace(step_name=name, status=status, result=SimpleNamespace(output=output))


def _chain_run_state(status, records):
    from types import SimpleNamespace

    return SimpleNamespace(status=status, step_records=records)


def _invoke_draft_with(run_state, tmp_path):
    """Invoke sw draft with adapter + runner mocked; return (result, captured pipeline)."""
    project_dir = _init_project(tmp_path, "chain-proj")
    with (
        patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_create,
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
    ):
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.llm.model = "test-model"
        mock_create.return_value = (settings, MagicMock(), MagicMock())
        mock_runner_class.return_value.run = AsyncMock(return_value=run_state)
        result = runner.invoke(app, ["draft", "greeter", "--project", str(project_dir)])
        pipeline = (
            mock_runner_class.call_args.args[0] if mock_runner_class.call_args else None
        )
    return result, pipeline


class TestDraftChain:
    """The inline chain: pipeline shape, inline report, exit codes (FR-1/2/3/6)."""

    def _happy_records(self):
        from specweaver.core.flow.engine.state import StepStatus

        return [
            _rec("draft_spec", StepStatus.PASSED, {"path": "specs/greeter_spec.md"}),
            _rec("validate_spec", StepStatus.PASSED, {"total": 12, "passed": 12, "results": []}),
            _rec(
                "review_spec",
                StepStatus.PASSED,
                {"verdict": "accepted", "findings": []},
            ),
        ]

    def test_pipeline_has_three_steps_with_exact_gates(self, tmp_path: Path) -> None:
        """[Happy] the built PipelineDefinition chains draft -> validate -> review with the
        approved gates (all_passed/abort; accepted/loop_back->draft_spec/max_retries=2)."""
        from specweaver.core.flow.engine.models import GateCondition, GateType, OnFailAction
        from specweaver.core.flow.engine.state import RunStatus

        run_state = _chain_run_state(RunStatus.COMPLETED, self._happy_records())
        result, pipeline = _invoke_draft_with(run_state, tmp_path)

        assert pipeline is not None, result.output
        names = [s.name for s in pipeline.steps]
        assert names == ["draft_spec", "validate_spec", "review_spec"]
        v_gate = pipeline.steps[1].gate
        assert v_gate.type == GateType.AUTO
        assert v_gate.condition == GateCondition.ALL_PASSED
        assert v_gate.on_fail == OnFailAction.ABORT
        r_gate = pipeline.steps[2].gate
        assert r_gate.type == GateType.AUTO
        assert r_gate.condition == GateCondition.ACCEPTED
        assert r_gate.on_fail == OnFailAction.LOOP_BACK
        assert r_gate.loop_target == "draft_spec"
        assert r_gate.max_retries == 2

    def test_happy_report_shows_all_outcomes_and_drops_stale_message(
        self, tmp_path: Path
    ) -> None:
        """[Happy/FR-6] accept path: spec path + validation + verdict inline; the stale
        'sw check' handoff line is GONE; exit 0."""
        from specweaver.core.flow.engine.state import RunStatus

        run_state = _chain_run_state(RunStatus.COMPLETED, self._happy_records())
        result, _ = _invoke_draft_with(run_state, tmp_path)

        assert result.exit_code == 0, result.output
        assert "greeter_spec.md" in result.output
        assert "12" in result.output  # validation rules surfaced
        assert "accepted" in result.output.lower()
        assert "sw check" not in result.output  # stale manual handoff removed (FR-6)

    def test_review_rejected_exhausted_exits_nonzero_with_findings(
        self, tmp_path: Path
    ) -> None:
        """[Degradation] review rejected until retries exhausted -> non-zero exit and the
        findings are surfaced."""
        from specweaver.core.flow.engine.state import RunStatus, StepStatus

        records = self._happy_records()
        records[2] = _rec(
            "review_spec",
            StepStatus.FAILED,
            {"verdict": "rejected", "findings": ["Purpose section vague"]},
        )
        run_state = _chain_run_state(RunStatus.FAILED, records)
        result, _ = _invoke_draft_with(run_state, tmp_path)

        assert result.exit_code != 0
        assert "rejected" in result.output.lower()
        assert "Purpose section vague" in result.output

    def test_validation_abort_reports_rule_failures(self, tmp_path: Path) -> None:
        """[Boundary] validate_spec fails -> abort; rule failures reported; non-zero."""
        from specweaver.core.flow.engine.state import RunStatus, StepStatus

        records = [
            self._happy_records()[0],
            _rec(
                "validate_spec",
                StepStatus.FAILED,
                {
                    "total": 12,
                    "passed": 10,
                    "results": [
                        {"rule_id": "S03", "status": "FAIL", "message": "stranger test failed"}
                    ],
                },
            ),
        ]
        run_state = _chain_run_state(RunStatus.FAILED, records)
        result, _ = _invoke_draft_with(run_state, tmp_path)

        assert result.exit_code != 0
        assert "S03" in result.output

    def test_missing_outputs_degrade_gracefully(self, tmp_path: Path) -> None:
        """[Hostile] records with None results / missing keys -> report degrades, no crash."""
        from types import SimpleNamespace

        from specweaver.core.flow.engine.state import RunStatus, StepStatus

        records = [
            SimpleNamespace(step_name="draft_spec", status=StepStatus.PASSED, result=None),
        ]
        run_state = _chain_run_state(RunStatus.FAILED, records)
        result, _ = _invoke_draft_with(run_state, tmp_path)
        assert result.exit_code != 0  # not completed
        # no traceback in output
        assert "Traceback" not in result.output

    def test_built_pipeline_passes_validate_flow(self, tmp_path: Path) -> None:
        """[G4/Boundary] the inline chain satisfies the engine's own flow validation
        (backward loop_target, gate coherence) — a direct tripwire against reordering."""
        from specweaver.workflows.review.interfaces.cli import _build_draft_pipeline

        pipeline = _build_draft_pipeline("greeter")
        pipeline.validate_flow()  # must not raise
