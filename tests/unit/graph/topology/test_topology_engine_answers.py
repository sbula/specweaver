# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The module graph's engine gives the same answers whatever library is under it.

Proves: TECH-088 FR-7

Written against the hand-written engine before it moved onto networkx, and green there: these are
today's answers, pinned. networkx alone answers three of them differently (the start of a cycle,
the centre of a neighbourhood, a missing node), so each is asserted exactly.

| Bucket | Case |
|---|---|
| Happy | a chain's dependencies and impact; a two-cycle and a three-cycle, each sorted |
| Boundary | a self-loop is a cycle; depth 0 is empty; depth 100 is cut at the limit; the start is never its own neighbour |
| Degradation | a node with no edges has no neighbours, dependencies or impact |
| Hostile | a node the graph never saw answers empty, never raises |
"""

from __future__ import annotations

import pytest

from specweaver.graph.topology.engine import TopologyEngine


def _engine(*edges: tuple[str, str]) -> TopologyEngine:
    engine = TopologyEngine()
    for source, target in edges:
        engine.add_edge(source, target)
    return engine


def test_a_chain_answers_its_dependencies_and_impact() -> None:
    engine = _engine(("a", "b"), ("b", "c"))

    assert engine.traverse("a", forward=True) == {"b", "c"}
    assert engine.traverse("c", forward=False) == {"a", "b"}
    assert engine.get_forward("a") == {"b"}
    assert engine.get_reverse("b") == {"a"}


def test_the_start_of_a_cycle_reaches_itself() -> None:
    engine = _engine(("a", "b"), ("b", "a"))

    assert engine.traverse("a", forward=True) == {"a", "b"}
    assert engine.traverse("a", forward=False) == {"a", "b"}


def test_a_start_off_the_cycle_does_not_reach_itself() -> None:
    engine = _engine(("x", "a"), ("a", "b"), ("b", "a"))

    assert engine.traverse("x", forward=True) == {"a", "b"}


def test_cycles_are_each_sorted_and_count_a_self_loop() -> None:
    engine = _engine(
        ("b", "a"), ("a", "b"), ("c", "c"), ("e", "d"), ("d", "f"), ("f", "e"), ("g", "h")
    )

    assert {tuple(cycle) for cycle in engine.cycles()} == {("a", "b"), ("c",), ("d", "e", "f")}


def test_a_chain_has_no_cycle() -> None:
    assert _engine(("a", "b"), ("b", "c")).cycles() == []


def test_a_neighbourhood_never_holds_its_start() -> None:
    engine = _engine(("a", "b"), ("b", "a"), ("c", "a"))

    assert engine.neighbors_within("a", depth=1) == {"b", "c"}
    assert engine.neighbors_within("a", depth=2) == {"b", "c"}


def test_a_neighbourhood_looks_both_ways() -> None:
    engine = _engine(("a", "b"), ("b", "c"), ("c", "d"))

    assert engine.neighbors_within("b", depth=1) == {"a", "c"}
    assert engine.neighbors_within("b", depth=2) == {"a", "c", "d"}


@pytest.mark.parametrize("depth", [0, -1])
def test_no_depth_is_no_neighbourhood(depth: int) -> None:
    assert _engine(("a", "b")).neighbors_within("a", depth=depth) == set()


def test_a_deep_request_is_cut_at_the_limit() -> None:
    engine = _engine(*((str(i), str(i + 1)) for i in range(9)))

    assert engine.neighbors_within("0", depth=100) == {"1", "2", "3", "4", "5"}


def test_a_lone_node_has_nothing_around_it() -> None:
    engine = TopologyEngine()
    engine.add_node("solo")

    assert engine.nodes == {"solo"}
    assert engine.traverse("solo", forward=True) == set()
    assert engine.neighbors_within("solo", depth=3) == set()
    assert engine.cycles() == []


def test_a_node_the_graph_never_saw_answers_empty() -> None:
    engine = _engine(("a", "b"))

    assert engine.get_forward("ghost") == set()
    assert engine.get_reverse("ghost") == set()
    assert engine.traverse("ghost", forward=True) == set()
    assert engine.traverse("ghost", forward=False) == set()
    assert engine.neighbors_within("ghost", depth=2) == set()


def test_answers_are_copies() -> None:
    engine = _engine(("a", "b"))

    engine.get_forward("a").add("z")
    engine.nodes.add("z")

    assert engine.get_forward("a") == {"b"}
    assert engine.nodes == {"a", "b"}
