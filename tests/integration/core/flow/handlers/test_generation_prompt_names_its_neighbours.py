# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Code generation tells the model which modules the spec's module works with.

Proves: TECH-088 FR-2

The run comes from the real run setup on real `context.yaml` files; before `TECH-088` the
generation prompt raised `AttributeError` on the list the run setup stores.

| Bucket | Case |
|---|---|
| Happy | generating for `billing` puts `payments (direct dependency)` in the prompt |
| Boundary | a module no `context.yaml` names gets no topology line |
| Degradation | — the prompt builder is pure; its own failures are its unit tests' |
| Hostile | — the neighbours come from files the test writes, not from input it controls |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.models import PipelineStep
from specweaver.core.flow.handlers.generation import _generation_prompt
from specweaver.interfaces.run_setup.builder import build_run_sync
from tests.fixtures.module_graph_project import module_graph_project, run_request

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_STEP = PipelineStep(name="generate", action="generate", target="code")


async def _prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str) -> str:
    db, root = module_graph_project(tmp_path, monkeypatch)
    context = build_run_sync(run_request(db, root, module))
    return (await _generation_prompt(context, _STEP, instructions="write it")).build()


async def test_the_generation_prompt_names_the_neighbour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = await _prompt(tmp_path, monkeypatch, "billing")

    assert "payments (direct dependency): Moves money." in prompt


async def test_an_unnamed_module_gets_no_topology_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = await _prompt(tmp_path, monkeypatch, "orphan")

    assert "(direct dependency)" not in prompt
