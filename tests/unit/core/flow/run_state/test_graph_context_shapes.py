# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A wrong shape in the module-graph fields fails where the run is built, not in a handler.

Proves: TECH-088 FR-1

| Bucket | Case |
|---|---|
| Happy | a `TopologyNode` and a `TopologyGraph` are accepted |
| Boundary | all three fields default to `None` |
| Degradation | — a model has no dependency to fail; the refusal itself is the degradation path |
| Hostile | a list, a string and a context record are refused as the boundary or the graph; a neighbour's context record is not a boundary, though it carries `mcp_servers` |
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from specweaver.commons.topology_context import TopologyContext
from specweaver.core.flow.run_state.run_context import GraphContext
from specweaver.graph.topology.engine import TopologyEngine
from specweaver.graph.topology.topology import TopologyGraph, TopologyNode

_CONTEXT = TopologyContext(name="payments", purpose="p", archetype="a", relationship="direct")


def test_the_real_shapes_are_accepted() -> None:
    node = TopologyNode(name="billing", level="", purpose="", archetype="")
    graph = TopologyGraph({"billing": node}, TopologyEngine())

    context = GraphContext(related_contexts=[_CONTEXT], target_boundary=node, module_graph=graph)

    assert context.target_boundary is node
    assert context.module_graph is graph


def test_the_fields_default_to_none() -> None:
    context = GraphContext()

    assert (context.related_contexts, context.target_boundary, context.module_graph) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize("wrong", [[_CONTEXT], "billing", Path("billing"), _CONTEXT])
def test_a_wrong_boundary_is_refused(wrong: object) -> None:
    with pytest.raises(ValidationError):
        GraphContext(target_boundary=wrong)


@pytest.mark.parametrize("wrong", [[_CONTEXT], "graph", _CONTEXT])
def test_a_wrong_graph_is_refused(wrong: object) -> None:
    with pytest.raises(ValidationError):
        GraphContext(module_graph=wrong)


def test_the_one_field_for_every_meaning_is_gone() -> None:
    """The old `topology` slot held four meanings; nothing may bring it back."""
    assert "topology" not in GraphContext.model_fields
