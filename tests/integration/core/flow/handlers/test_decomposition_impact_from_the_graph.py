# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Decomposition takes impact sets from the module graph and hands the decomposer flat contexts.

Proves: TECH-088 FR-4

`C-FLOW-03` starts a component only if its impact does not overlap a running one. The impact came
from `.impact_of` on the run's topology slot, which held a list: a component with target modules
raised `AttributeError`. The decomposer was handed that list wrapped in another list.

| Bucket | Case |
|---|---|
| Happy | a component targeting `payments` reaches `billing`, which consumes it |
| Boundary | a component with no target modules reaches only itself |
| Degradation | a run with no `context.yaml` gives impact sets of the component alone |
| Hostile | — the graph comes from files the test writes, not from input it controls |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.decompose import DecomposeFeatureHandler, _impacts_of
from specweaver.interfaces.run_setup.builder import build_run_sync
from tests.fixtures.module_graph_project import module_graph_project, run_request

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def test_a_target_module_reaches_its_consumers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch)
    context = build_run_sync(run_request(db, root, "billing"))

    impacts = _impacts_of("A", {"A": {"target_modules": ["payments"]}}, context)

    assert impacts == {"A", "billing"}


def test_a_component_without_targets_reaches_only_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch)
    context = build_run_sync(run_request(db, root, "billing"))

    assert _impacts_of("A", {"A": {}}, context) == {"A"}


def test_no_manifests_means_the_component_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch, manifests=False)
    context = build_run_sync(run_request(db, root, "billing"))

    assert _impacts_of("A", {"A": {"target_modules": ["payments"]}}, context) == {"A"}


class _StopError(Exception):
    """Ends the step once the decomposer has been called."""


async def test_the_decomposer_gets_a_flat_list_of_contexts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch)
    seen: dict[str, Any] = {}

    async def _decompose(_self: Any, **kwargs: Any) -> Any:
        seen.update(kwargs)
        raise _StopError

    context = build_run_sync(run_request(db, root, "billing", StepAction.DECOMPOSE))
    step = PipelineStep(name="d", action=StepAction.DECOMPOSE, target=StepTarget.FEATURE)
    # The model is not the claim: the decomposer is doubled, so the step needs no settings.
    with (
        patch("specweaver.core.flow.handlers._llm.llm_for_step", return_value=(MagicMock(), None)),
        patch("specweaver.core.flow.handlers.decompose.FeatureDecomposer.decompose", _decompose),
    ):
        result = await DecomposeFeatureHandler().execute(step, context)

    assert "topology_contexts" in seen, result.error_message

    assert [c.name for c in seen["topology_contexts"]] == ["payments"]
