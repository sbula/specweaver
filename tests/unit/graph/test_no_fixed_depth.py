# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No fixed traversal depth: a caller passes one, or `None` for everything.

Proves: A-SENS-02 FR-1, FR-2, FR-3

Both in-memory engines cut a neighbourhood at 5 hops, whatever a caller asked for (`TECH-088`
FR-9, superseded by FR-1). A caller that wants a limit passes it; one that passes nothing gets the
whole connected part of the graph. The shared cases in `tests/traversal_cases.py` hold the depth of
every node, so each depth asked for must return exactly the nodes at or below it.

| Bucket | Case |
|---|---|
| Happy | every shared case, `depth=None`: both engines reach every node |
| Boundary | depth 0, 1, 2 and the deepest node's depth return exactly the nodes at or below it; a call with no depth is `None` |
| Degradation | — a pure traversal has no dependency to fail; a missing start keeps today's answer |
| Hostile | a string, a float and a bool are a `TypeError`, a negative depth a `ValueError`, each naming the value; no constant and no `min(depth, …)` is left in `src/` |
"""

from __future__ import annotations

import re
from pathlib import Path

import networkx as nx
import pytest

from specweaver.graph.core.engine import models
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.topology.engine import TopologyEngine
from tests.traversal_cases import CASES, Case

_ROOT = Path(__file__).resolve().parents[3]


def _code(case: Case) -> InMemoryGraphEngine:
    engine = InMemoryGraphEngine()
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_edges_from(case.edges)
    engine.load_semantic_digraph(graph)
    return engine


def _modules(case: Case) -> TopologyEngine:
    engine = TopologyEngine()
    for a, b in case.edges:
        engine.add_edge(a, b)
    return engine


def _within(case: Case, depth: int) -> set[str]:
    return {node for node, d in case.depths.items() if d <= depth}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_no_depth_reaches_every_node(case: Case) -> None:
    assert set(_code(case).extract_subgraph(case.start, None).nodes) == set(case.depths)
    assert _modules(case).neighbors_within(case.start, None) == set(case.depths) - {case.start}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_each_depth_returns_the_nodes_at_or_below_it(case: Case) -> None:
    code, modules = _code(case), _modules(case)
    for depth in sorted({1, 2, max(case.depths.values())}):
        expected = _within(case, depth)
        assert set(code.extract_subgraph(case.start, depth).nodes) == expected, depth
        assert modules.neighbors_within(case.start, depth) == expected - {case.start}, depth


def test_a_call_with_no_depth_is_unbounded() -> None:
    (chain,) = [c for c in CASES if c.name == "chain of 10000"]

    assert len(_code(chain).extract_subgraph(chain.start).nodes) == 10_000
    assert len(_modules(chain).neighbors_within(chain.start)) == 9_999


def test_depth_zero_keeps_todays_answer() -> None:
    (chain,) = [c for c in CASES if c.name == "chain of 7"]

    assert set(_code(chain).extract_subgraph(chain.start, 0).nodes) == {chain.start}
    assert _modules(chain).neighbors_within(chain.start, 0) == set()


@pytest.mark.parametrize("depth", ["3", 2.0, True, False])
def test_a_depth_that_is_not_an_int_is_refused_by_name(depth: object) -> None:
    (chain,) = [c for c in CASES if c.name == "chain of 7"]

    with pytest.raises(TypeError, match=re.escape(repr(depth))):
        _code(chain).extract_subgraph(chain.start, depth)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=re.escape(repr(depth))):
        _modules(chain).neighbors_within(chain.start, depth)  # type: ignore[arg-type]


def test_a_negative_depth_is_refused_by_name() -> None:
    (chain,) = [c for c in CASES if c.name == "chain of 7"]

    with pytest.raises(ValueError, match="-1"):
        _code(chain).extract_subgraph(chain.start, -1)
    with pytest.raises(ValueError, match="-1"):
        _modules(chain).neighbors_within(chain.start, -1)


def test_no_fixed_depth_is_left_in_the_source() -> None:
    src = _ROOT / "src" / "specweaver"
    capped = [
        f"{path.relative_to(src)}: {m.group(0)}"
        for path in src.rglob("*.py")
        for m in re.finditer(r"min\(depth, \w+\)|MAX_NEIGHBOURHOOD_DEPTH", path.read_text("utf-8"))
    ]

    assert not hasattr(models, "MAX_NEIGHBOURHOOD_DEPTH")
    assert capped == []


def test_no_test_asserts_a_limit_of_five() -> None:
    """FR-3: `TECH-088` FR-9's test went with the limit it proved."""
    assert not (_ROOT / "tests" / "unit" / "graph" / "test_one_depth_limit.py").exists()
