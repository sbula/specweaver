# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A real run writes rule results a real query reads back. `INT-US-04` SF-01 CB-2, the seam.

`ADR-003` puts the integration test on the story that creates the seam, so this sub-feature owns
it — no later story will write it.

> [!IMPORTANT]
> **The failing-step test is the one that matters, and it is why the plan was amended.**
> CB-2 as approved put the writer at the advance join point (`step_execution.py:474`, beside
> `hydrate_plan_context`). That line is reached **only when `resolve_outcome` returns `PROCEED`** —
> a validate step that fails and loops back returns `CONTINUE`, one that fails gateless or parks
> returns `RETURN`. At the planned position the table would have filled with passing runs and
> silently dropped every failure: the findings that trigger regeneration, and precisely what `FR-3`
> replays next.
>
> Symmetry with plan hydration was the reason for the original position and it was the wrong
> reason — hydration *should* only run on advance, because a failed step has no plan to hydrate.
> Persistence has the opposite requirement.

Proves: INT-US-04 FR-2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.models import (
    GateCondition,
    GateDefinition,
    GateType,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path


def _payload(rule_id: str, *findings: dict, status: str = "fail") -> dict:
    """`StepResult.output` in the shape `_rule_payload` builds it (CB-1)."""
    return {
        "results": [
            {
                "rule_id": rule_id,
                "status": status,
                "message": f"{rule_id} says so",
                "findings": list(findings),
            }
        ],
        "total": 1,
        "passed": 0 if status == "fail" else 1,
        "failed": 1 if status == "fail" else 0,
    }


def _finding(message: str, line: int = 7) -> dict:
    return {"message": message, "line": line, "severity": "error", "suggestion": "fix it"}


class _PassHandler:
    async def execute(self, step, context):
        return StepResult(status=StepStatus.PASSED, output={}, started_at="1", completed_at="2")


class _ValidateHandler:
    """Fails on the first attempt with findings, passes on the second."""

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, step, context):
        self.calls += 1
        if self.calls == 1:
            return StepResult(
                status=StepStatus.FAILED,
                output=_payload("S01", _finding("weasel word on line 7")),
                error_message="1 validation rules failed",
                started_at="1",
                completed_at="2",
            )
        return StepResult(
            status=StepStatus.PASSED,
            output=_payload("S01", status="pass"),
            started_at="1",
            completed_at="2",
        )


def _looping_pipeline() -> PipelineDefinition:
    return PipelineDefinition(
        name="validate_persistence",
        steps=[
            PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC),
            PipelineStep(
                name="validate_spec",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                gate=GateDefinition(
                    type=GateType.AUTO,
                    condition=GateCondition.ALL_PASSED,
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="draft",
                    max_retries=2,
                ),
            ),
        ],
    )


async def _run(tmp_path: Path, *, store: StateStore | None):
    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, _PassHandler())
    validator = _ValidateHandler()
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, validator)

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    runner = PipelineRunner(_looping_pipeline(), context, store=store, registry=registry)
    return await runner.run(), validator


@pytest.mark.integration
class TestValidationResultsPersistence:
    """The `D-INTL-01` → state-DB seam: a real run, a real query."""

    @pytest.mark.asyncio
    async def test_a_failing_validate_step_persists_its_findings(self, tmp_path: Path) -> None:
        """[Happy + regression] The row that the planned write point would have dropped.

        The run loops back once, so `validate_spec` executes twice: attempt 1 FAILS with a finding,
        attempt 2 passes. Both must be in the table — and at `step_execution.py:474` the failing
        one would not be, because a loop-back never reaches that line.
        """
        store = StateStore(tmp_path / "state.db")
        run, validator = await _run(tmp_path, store=store)

        assert validator.calls == 2, "the pipeline did not loop back — test is not exercising it"

        rows = store.get_validation_results(run.run_id)
        assert rows, "no rule results were persisted at all"

        failing = [r for r in rows if r["rule_status"] == "fail"]
        assert failing, (
            "the FAILING attempt was not persisted — this is the defect the write-point "
            f"correction exists for. Rows present: {rows}"
        )
        assert failing[0]["rule_id"] == "S01"
        assert failing[0]["message"] == "weasel word on line 7"
        assert failing[0]["line"] == 7
        assert failing[0]["severity"] == "error"
        assert failing[0]["step_name"] == "validate_spec"

    @pytest.mark.asyncio
    async def test_both_attempts_are_readable_and_distinguishable(self, tmp_path: Path) -> None:
        """[Boundary] Append-only across a retry: the earlier failure is not overwritten."""
        store = StateStore(tmp_path / "state.db")
        run, _ = await _run(tmp_path, store=store)

        rows = store.get_validation_results(run.run_id, step="validate_spec")
        statuses = [r["rule_status"] for r in rows]
        assert "fail" in statuses and "pass" in statuses, (
            f"both attempts must survive; got {statuses}"
        )
        assert len({r["attempt"] for r in rows}) == 2, (
            f"attempts must be distinguishable, got {sorted(r['attempt'] for r in rows)}"
        )

    @pytest.mark.asyncio
    async def test_run_tests_writes_no_rows(self, tmp_path: Path) -> None:
        """[Boundary] D-5 — `run_tests` is VALIDATE+TESTS and its payload has no `rule_id`.

        Persisting it would make the table mean two different things.
        """
        store = StateStore(tmp_path / "state.db")
        registry = StepHandlerRegistry()

        class _QAHandler:
            async def execute(self, step, context):
                return StepResult(
                    status=StepStatus.PASSED,
                    output={"passed": 3, "failed": 0, "total": 3},
                    started_at="1",
                    completed_at="2",
                )

        registry.register(StepAction.VALIDATE, StepTarget.TESTS, _QAHandler())
        pipeline = PipelineDefinition(
            name="qa_only",
            steps=[
                PipelineStep(name="run_tests", action=StepAction.VALIDATE, target=StepTarget.TESTS)
            ],
        )
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        run = await PipelineRunner(pipeline, context, store=store, registry=registry).run()

        assert store.get_validation_results(run.run_id) == []

    @pytest.mark.asyncio
    async def test_a_run_without_a_store_does_not_crash(self, tmp_path: Path) -> None:
        """[Degradation] `store=None` is a supported configuration; the writer must be a no-op."""
        run, validator = await _run(tmp_path, store=None)
        assert validator.calls == 2
        assert run is not None
