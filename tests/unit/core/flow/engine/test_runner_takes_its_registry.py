# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The caller hands `PipelineRunner` its step-handler registry; the engine builds none.

Proves: TECH-081 FR-12

| Bucket | Case |
|---|---|
| Happy | the runner uses the registry it was given |
| Boundary | `registry` has no default in the signature |
| Degradation | a runner built without a registry fails at once, not at the first step |
| Hostile | a registry passed positionally is refused (keyword-only) |
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.run_state.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path


def _context(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")


def _pipeline() -> PipelineDefinition:
    return PipelineDefinition(name="empty", steps=[])


def test_the_runner_uses_the_registry_it_was_given(tmp_path: Path) -> None:
    registry = StepHandlerRegistry()

    runner = PipelineRunner(_pipeline(), _context(tmp_path), registry=registry)

    assert runner.registry is registry


def test_registry_has_no_default() -> None:
    param = inspect.signature(PipelineRunner).parameters["registry"]

    assert param.default is inspect.Parameter.empty
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_a_runner_without_a_registry_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="registry"):
        PipelineRunner(_pipeline(), _context(tmp_path))  # type: ignore[call-arg]


def test_a_positional_registry_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        PipelineRunner(_pipeline(), _context(tmp_path), StepHandlerRegistry())  # type: ignore[misc]
