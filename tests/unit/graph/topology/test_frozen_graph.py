# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A module graph cannot change once it is built.

Proves: TECH-088 FR-13

A step runs on a shallow copy of its run, so every step of a run shares one module graph. That is
safe only while nothing writes to it, so the graph freezes itself at the end of building: its
engine, the nodes it holds and the stale nodes it computed.

| Bucket | Case |
|---|---|
| Happy | a built graph answers every read |
| Boundary | an engine no graph has frozen still takes writes; stale seeds reach what they impact before the freeze |
| Degradation | — freezing has no dependency to fail |
| Hostile | `add_node`, `add_edge`, changing the caller's dict, assigning into `nodes`: none changes the graph |
"""

from __future__ import annotations

import pytest

from specweaver.graph.topology.engine import FrozenGraphError, TopologyEngine
from specweaver.graph.topology.topology import TopologyGraph, TopologyNode


def _node(name: str, *consumes: str) -> TopologyNode:
    return TopologyNode(
        name=name, level="module", purpose="", archetype="", consumes=list(consumes)
    )


def _built(nodes: dict[str, TopologyNode] | None = None, **kw: object) -> TopologyGraph:
    nodes = nodes if nodes is not None else {"a": _node("a", "b"), "b": _node("b")}
    return TopologyGraph(nodes, TopologyEngine(), **kw)  # type: ignore[arg-type]


def test_a_built_graph_still_answers() -> None:
    graph = _built()

    assert graph.dependencies_of("a") == {"b"}
    assert graph.consumers_of("b") == {"a"}
    assert set(graph.nodes) == {"a", "b"}


def test_a_built_graph_refuses_a_new_node() -> None:
    graph = _built()

    with pytest.raises(FrozenGraphError):
        graph._engine.add_node("c")


def test_a_built_graph_refuses_a_new_edge() -> None:
    graph = _built()

    with pytest.raises(FrozenGraphError):
        graph._engine.add_edge("b", "a")
    assert graph.consumers_of("a") == set()


def test_an_engine_no_graph_froze_still_takes_writes() -> None:
    engine = TopologyEngine()
    engine.add_edge("a", "b")

    assert engine.get_forward("a") == {"b"}


def test_changing_the_callers_dict_changes_nothing() -> None:
    nodes = {"a": _node("a")}
    graph = _built(nodes)

    nodes["z"] = _node("z")

    assert set(graph.nodes) == {"a"}


def test_the_nodes_cannot_be_assigned() -> None:
    graph = _built()

    with pytest.raises(TypeError):
        graph.nodes["z"] = _node("z")  # type: ignore[index]


def test_stale_seeds_reach_what_they_impact() -> None:
    graph = _built(stale_seeds={"b"})

    assert graph.stale_nodes == {"a", "b"}


def test_the_stale_nodes_cannot_be_changed() -> None:
    graph = _built(stale_seeds={"b"})

    graph.stale_nodes.add("z")

    assert graph.stale_nodes == {"a", "b"}
