# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The coder's code runs in a container in a dual run, and in any run of a project with kept scenarios.

Proves: B-FLOW-01 FR-21
Proves: B-FLOW-01 FR-18

One rule, used by every step that runs the coder's code: the test step, C03/C04 and lint fix.

| Bucket | Case |
|---|---|
| Happy | the coder side of a dual run, or a project with a kept set, runs in a container |
| Boundary | a project with no kept set and no dual run keeps its own setting |
| Degradation | a kept set and no container: warn, and run as the settings say |
| Hostile | every step that runs the coder's code asks the same rule; the dual run flags its coder side |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

import specweaver.core.flow.handlers.coder_sandbox as choice
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import RunStatus
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.run_context import RunContext, RunHandle
from specweaver.sandbox.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path


def _context(tmp_path: Path, *, dual: bool = False) -> RunContext:
    return RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "specs" / "greet_spec.md",
        run=RunHandle(dual_side="coder" if dual else None),
    )


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path.parent / f"{tmp_path.name}-store"

    monkeypatch.setattr(
        "specweaver.core.flow.handlers.scenario_store.scenario_store", lambda context: path
    )
    return path


def _keep_a_set(store: Path) -> None:
    (store / "generated").mkdir(parents=True)
    (store / "generated" / "test_greet_scenarios.py").write_text("x = 1\n")


def _available(monkeypatch: pytest.MonkeyPatch, answer: bool) -> None:
    monkeypatch.setattr(choice, "container_available", lambda root: answer)


def test_a_plain_run_keeps_its_setting(
    tmp_path: Path, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _available(monkeypatch, True)
    assert choice.coder_sandbox(_context(tmp_path)) is None


@pytest.mark.parametrize("why", ["dual-run", "kept-set"])
def test_the_coder_runs_in_a_container(
    tmp_path: Path, store: Path, monkeypatch: pytest.MonkeyPatch, why: str
) -> None:
    _available(monkeypatch, True)
    if why == "kept-set":
        _keep_a_set(store)

    settings = choice.coder_sandbox(_context(tmp_path, dual=why == "dual-run"))

    assert settings is not None and settings.execution_mode == "container"


def test_a_kept_set_without_a_container_warns_and_goes_on(
    tmp_path: Path, store: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _available(monkeypatch, False)
    _keep_a_set(store)

    with caplog.at_level(logging.WARNING):
        settings = choice.coder_sandbox(_context(tmp_path))

    assert settings is None
    assert "container" in caplog.text


def _ok_atom() -> MagicMock:
    atom = MagicMock()
    atom.run.return_value = AtomResult(
        status=AtomStatus.SUCCESS, message="ok", exports={"passed": 1, "failed": 0, "total": 1}
    )
    return atom


@pytest.mark.asyncio
async def test_the_test_step_asks_the_rule(
    tmp_path: Path, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.core.flow.handlers.validation import ValidateTestsHandler

    _available(monkeypatch, True)
    step = PipelineStep(name="run_tests", action=StepAction.VALIDATE, target=StepTarget.TESTS)
    with patch(
        "specweaver.sandbox.qa_runner.core.atom.QARunnerAtom", return_value=_ok_atom()
    ) as built:
        await ValidateTestsHandler().execute(step, _context(tmp_path, dual=True))

    assert built.call_args.kwargs["sandbox_settings"].execution_mode == "container"


def test_lint_fix_asks_the_rule(
    tmp_path: Path, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.core.flow.handlers.lint_fix import LintFixHandler

    _available(monkeypatch, True)
    with patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom") as built:
        LintFixHandler()._get_atom(_context(tmp_path, dual=True))

    assert built.call_args.kwargs["sandbox_settings"].execution_mode == "container"


def test_c03_and_c04_get_the_settings(tmp_path: Path) -> None:
    from specweaver.core.config.settings import SandboxSettings
    from specweaver.core.flow.handlers.validation_hydrator import hydrate_code_validation_context

    pipeline = MagicMock()
    pipeline.steps = [MagicMock(rule="C03")]
    code = tmp_path / "src" / "greet.py"
    code.parent.mkdir(parents=True)
    code.write_text("x = 1\n")
    container = SandboxSettings(execution_mode="container")
    with patch(
        "specweaver.sandbox.qa_runner.core.atom.QARunnerAtom", return_value=_ok_atom()
    ) as built:
        hydrate_code_validation_context(pipeline, code, tmp_path, sandbox_settings=container)

    assert built.call_args.kwargs["sandbox_settings"] is container


@pytest.mark.asyncio
async def test_the_dual_run_flags_its_coder_side(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ArbitrateDualPipelineHandler, "container_available", staticmethod(lambda root: True)
    )
    monkeypatch.setattr(
        ArbitrateDualPipelineHandler, "isolation_refusal", staticmethod(lambda context: None)
    )
    monkeypatch.setattr(
        ArbitrateDualPipelineHandler, "review_refusal", staticmethod(lambda context: None)
    )
    flagged: list[bool] = []

    class _Spawner:
        def spawn(self, pipeline: Any, feedback: Any = None, side: str | None = None) -> Any:
            flagged.append(side == "coder")

            class _Done:
                async def run(self, parent_run_id: str | None = None) -> Any:
                    class _Run:
                        status = RunStatus.COMPLETED

                    return _Run()

            return _Done()

    context = _context(tmp_path)
    context.run = RunHandle(run_id="r", pipeline_runner=_Spawner())
    step = PipelineStep(
        name="run_dual_pipelines", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
    )
    await ArbitrateDualPipelineHandler().execute(step, context)

    assert flagged == [True, False]
