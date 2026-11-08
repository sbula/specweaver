# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Both graph engines cut a neighbourhood at the same depth, written in one place.

Proves: TECH-088 FR-9

The module graph and the code graph each wrote `min(depth, 5)` of their own. Two copies of a limit
drift apart the first time one is changed.

| Bucket | Case |
|---|---|
| Happy | the limit is 5, in `graph/core/engine/models.py` |
| Boundary | a chain of ten is cut at the limit by the module graph's engine and by the code graph's |
| Degradation | — a constant has no dependency to fail |
| Hostile | no `min(depth, <number>)` is left anywhere in `src/` |
"""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

from specweaver.graph.core.engine import models
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import GraphEdge, GraphNode
from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind
from specweaver.graph.topology.engine import TopologyEngine

_SRC = Path(__file__).resolve().parents[3] / "src" / "specweaver"


def test_the_limit_is_five_and_lives_with_the_graph_models() -> None:
    assert models.MAX_NEIGHBOURHOOD_DEPTH == 5


def test_the_module_graph_cuts_at_the_limit() -> None:
    engine = TopologyEngine()
    for i in range(9):
        engine.add_edge(str(i), str(i + 1))

    reached = engine.neighbors_within("0", depth=100)

    assert reached == {str(i) for i in range(1, models.MAX_NEIGHBOURHOOD_DEPTH + 1)}


def test_the_code_graph_cuts_at_the_limit() -> None:
    engine = InMemoryGraphEngine()
    hashes = [f"h{i}" for i in range(10)]
    for h in hashes:
        engine.upsert_node(GraphNode(semantic_hash=h, kind=NodeKind.MODULE, name=h, file_id="f.py"))
    for a, b in pairwise(hashes):
        engine.upsert_edge(GraphEdge(source_hash=a, target_hash=b, kind=EdgeKind.CALLS))

    reached = set(engine.extract_subgraph("h0", depth=100).nodes)

    assert reached == set(hashes[: models.MAX_NEIGHBOURHOOD_DEPTH + 1])


def test_no_engine_writes_its_own_limit() -> None:
    own = [
        f"{path.relative_to(_SRC)}: {match.group(0)}"
        for path in _SRC.rglob("*.py")
        for match in re.finditer(r"min\(depth, \d+\)", path.read_text(encoding="utf-8"))
    ]

    assert own == []
