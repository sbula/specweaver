# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The sandbox takes the run's build tool: the plan, the image, the container and the dual run.

Proves: TECH-079 FR-7

A root with `pyproject.toml`, `Cargo.toml` and `Cargo.lock`, pinned to Rust: before TECH-079 the
sandbox detected `uv` from `pyproject.toml` and prepared Python in the Python image. Real handlers,
real executor and plan; no container engine is started.

| Bucket | Case |
|---|---|
| Happy | the coder's container gets the Rust image, the cargo fetch and cargo's environment |
| Boundary | the coder sandbox, the kept suite, the dual run and the readiness check ask for the run's build tool |
| Degradation | a container run without a build tool, or a build tool with no plan, is refused, naming what is missing |
| Hostile | a TypeScript (npm) dual run refuses, a Python one does not; an undecided run refuses every part |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.commons.project_profile import ProjectProfile, ProjectUndecidedError
from specweaver.core.config.settings import SandboxSettings
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.run_state.run_context import IsolationPolicy, RunContext, RunHandle
from specweaver.sandbox.language.core.runner_factory import qa_atom
from specweaver.workspace.project.prepare_plan import plan_for

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_RUST_IMAGE = "docker.io/library/rust:1-slim"


def _context(root: Path, **isolation: object) -> RunContext:
    for name, text in {
        "pyproject.toml": "[project]\nname = 'x'\n",
        "Cargo.toml": '[package]\nname = "p"\n',
        "Cargo.lock": "",
    }.items():
        (root / name).write_text(text, encoding="utf-8")
    return RunContext(
        project_path=root,
        spec_path=root / "specs" / "greet_spec.md",
        isolation=IsolationPolicy(**isolation),
        run=RunHandle(dual_side="coder"),
    )


def _coder_container(context: RunContext, asked: list[tuple[object, ...]]):
    def available(*args: object) -> bool:
        asked.append(args)
        return True

    with patch("specweaver.core.flow.handlers.coder_sandbox.container_available", available):
        return LintFixHandler()._get_atom(context)._runner._executor


def test_a_run_pinned_to_rust_prepares_rust_in_the_rust_image(tmp_path: Path) -> None:
    context = _context(tmp_path, profile=ProjectProfile("rust", "cargo"))
    asked: list[tuple[object, ...]] = []

    executor = _coder_container(context, asked)

    assert asked == [(tmp_path, "cargo")]
    assert executor._image == _RUST_IMAGE
    assert executor._toolchain_env()["CARGO_HOME"] == "/cache/cargo"
    assert plan_for(tmp_path, "cargo").route == "fetch"


def test_a_container_run_without_a_build_tool_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="build tool"):
        qa_atom(
            tmp_path,
            "python",
            sandbox_settings=SandboxSettings(execution_mode="container"),
        )


@pytest.mark.parametrize(
    ("profile", "refused"), [(("typescript", "npm"), True), (("python", "uv"), False)]
)
def test_only_a_python_dual_run_is_let_through(
    tmp_path: Path, profile: tuple[str, str], refused: bool
) -> None:
    from specweaver.core.flow.handlers.dual_pipeline import _isolation_refusal

    context = _context(tmp_path, profile=ProjectProfile(*profile))
    with patch(
        "specweaver.core.flow.run_state.scenario_store.scenario_store",
        lambda _context: tmp_path / "store",
    ):
        refusal = _isolation_refusal(context)

    assert (refusal is not None) is refused
    if refused:
        assert "proven for Python projects only" in (refusal or "")


def test_an_undecided_run_refuses_the_coder_container(tmp_path: Path) -> None:
    context = _context(tmp_path, undecided="set [implement] language in specweaver.toml")

    with pytest.raises(ProjectUndecidedError, match=r"set \[implement\] language"):
        _coder_container(context, [])


def test_the_kept_suite_asks_for_the_run_build_tool(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from specweaver.core.flow.handlers.acceptance import run_acceptance

    context = _context(tmp_path, profile=ProjectProfile("rust", "cargo"))
    asked: list[tuple[object, ...]] = []
    fresh = [{"spec": "specs/greet_spec.md", "fresh": True, "tests": "test_greet.py"}]

    with (
        patch("specweaver.core.flow.handlers.reviewed_spec.kept_sets", lambda _c: fresh),
        patch("specweaver.core.flow.run_state.scenario_store.scenario_store", lambda _c: tmp_path),
        patch(
            "specweaver.core.flow.handlers.acceptance.container_available",
            lambda *args: asked.append(args) or False,
        ),
    ):
        run_acceptance(context, MagicMock())

    assert asked == [(tmp_path, "cargo")]


async def test_a_dual_run_asks_for_the_run_build_tool(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
    from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler

    context = _context(tmp_path, profile=ProjectProfile("python", ""))
    context.run = RunHandle(pipeline_runner=MagicMock())
    asked: list[tuple[object, ...]] = []
    handler = ArbitrateDualPipelineHandler()
    handler.isolation_refusal = lambda _c: None  # type: ignore[method-assign]
    handler.container_available = lambda *args: asked.append(args) or False  # type: ignore[method-assign]
    step = PipelineStep(name="dual", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)

    await handler.execute(step, context)

    assert asked == [(tmp_path, "")]


def test_the_readiness_check_builds_the_image_of_the_build_tool(tmp_path: Path) -> None:
    from specweaver.sandbox.execution.sandbox_image import sandbox_ready

    built: list[str] = []

    def ensure(image: str, _engine: str, _run: object) -> bool:
        built.append(image)
        return True

    sandbox_ready(
        tmp_path,
        "cargo",
        which={"podman": "/usr/bin/podman"}.get,
        probe=lambda e: True,
        ensure=ensure,
    )

    assert built == [_RUST_IMAGE]


def test_an_unknown_build_tool_has_no_plan(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no prepare plan for build tool 'ant'"):
        plan_for(tmp_path, "ant")
