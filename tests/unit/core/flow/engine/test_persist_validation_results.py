# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`persist_validation_results` — its guards and its failure path. `INT-US-04` SF-01 CB-2.

The happy path is covered by the integration seam. These are the three branches it cannot reach:
a store that raises, a malformed payload, and a missing step record.

The first exists because the plan **promised** it. D-7: *"Never raises. Logs WARNING with the run
id, and that path carries its own test."* It did not, until this file — an `except Exception` in
the pipeline loop that has never executed is indistinguishable from one that does not work
(`TECH-032`).

Proves: INT-US-04 FR-2.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.core.flow.engine.step_execution import persist_validation_results

if TYPE_CHECKING:
    import pytest as _pytest  # noqa: F401

_RESULTS = [{"rule_id": "S01", "status": "fail", "message": "m", "findings": []}]


def _run(*, records: list[StepRecord] | None = None) -> PipelineRun:
    return PipelineRun(
        run_id="run-1",
        pipeline_name="p",
        project_name="proj",
        spec_path="specs/s.md",
        status=RunStatus.RUNNING,
        current_step=0,
        step_records=records if records is not None else [StepRecord(step_name="validate_spec")],
        started_at="1",
        updated_at="1",
    )


def _step() -> PipelineStep:
    return PipelineStep(name="validate_spec", action=StepAction.VALIDATE, target=StepTarget.SPEC)


def _result(output: object) -> StepResult:
    return StepResult(status=StepStatus.FAILED, output=output, started_at="1", completed_at="2")


def _runner(store: object) -> SimpleNamespace:
    return SimpleNamespace(_store=store)


class TestPersistValidationResults:
    """The three branches the integration seam cannot reach."""

    def test_a_store_that_raises_is_swallowed_and_logged(self, caplog) -> None:
        """[Degradation] V-1 — D-7's promise, finally kept.

        A pipeline must not die because an audit row could not be written. The run id has to be in
        the message: without it a WARNING in a fan-out run names no run and is unactionable.
        """
        store = MagicMock()
        store.save_validation_results.side_effect = OSError("database is locked")

        with caplog.at_level(logging.WARNING):
            persist_validation_results(
                _runner(store), _run(), _step(), 0, _result({"results": _RESULTS})
            )

        store.save_validation_results.assert_called_once()
        assert any("run-1" in r.getMessage() for r in caplog.records), (
            f"no WARNING naming the run: {caplog.text}"
        )
        assert "validate_spec" in caplog.text

    def test_output_without_results_writes_nothing(self) -> None:
        """[Hostile] V-2 — any handler may return any dict; the guard must hold."""
        store = MagicMock()
        persist_validation_results(_runner(store), _run(), _step(), 0, _result({"passed": 3}))
        store.save_validation_results.assert_not_called()

    def test_a_non_list_results_value_writes_nothing(self) -> None:
        """[Hostile] V-2 — `results` present but the wrong type must not reach `enumerate`."""
        store = MagicMock()
        persist_validation_results(_runner(store), _run(), _step(), 0, _result({"results": "nope"}))
        store.save_validation_results.assert_not_called()

    def test_a_missing_step_record_falls_back_to_attempt_one(self) -> None:
        """[Boundary] V-3 — a wrong attempt silently corrupts the append-only history.

        `step_idx` can exceed the record list when a pipeline is resumed against an edited
        definition — the same mismatch `rehydrate_from_records` guards against by name.
        """
        store = MagicMock()
        persist_validation_results(
            _runner(store), _run(records=[]), _step(), 5, _result({"results": _RESULTS})
        )
        assert store.save_validation_results.call_args.kwargs["attempt"] == 1

    def test_a_falsy_attempt_falls_back_to_one(self) -> None:
        """[Boundary] V-3 — `attempt=0` would sort a row before every real attempt."""
        store = MagicMock()
        persist_validation_results(
            _runner(store),
            _run(records=[StepRecord(step_name="validate_spec", attempt=0)]),
            _step(),
            0,
            _result({"results": _RESULTS}),
        )
        assert store.save_validation_results.call_args.kwargs["attempt"] == 1

    def test_the_records_attempt_is_used_when_present(self) -> None:
        """[Happy] The durable counter, not a constant — `TECH-033`'s reason for moving it there."""
        store = MagicMock()
        persist_validation_results(
            _runner(store),
            _run(records=[StepRecord(step_name="validate_spec", attempt=3)]),
            _step(),
            0,
            _result({"results": _RESULTS}),
        )
        assert store.save_validation_results.call_args.kwargs["attempt"] == 3

    def test_no_store_configured_is_a_no_op(self) -> None:
        """[Degradation] `store=None` is a supported runner configuration."""
        persist_validation_results(
            _runner(None), _run(), _step(), 0, _result({"results": _RESULTS})
        )

    def test_a_non_validate_step_is_skipped(self) -> None:
        """[Boundary] D-5 — only VALIDATE+SPEC/CODE carry rule results."""
        store = MagicMock()
        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        persist_validation_results(_runner(store), _run(), step, 0, _result({"results": _RESULTS}))
        store.save_validation_results.assert_not_called()
