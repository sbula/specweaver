# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The in-memory graph engine: mutation under a lock, and bounded subgraph extraction.

Proves: B-SENS-02 FR-6
Proves: TECH-004 FR-1

Cited from `INT-US-10-MIG`. Two independent mutants die here, which is why the citation is trusted:
removing the depth cap (`max_depth = min(requested_depth, 5)` -> `requested_depth`) and forcing the
ego-graph radius to 1 each fail a test. A single surviving mutant would have meant the depth half of
FR-6 was unconstrained.
"""

import threading

from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import GraphEdge, GraphNode
from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind


def test_engine_thread_safety():
    """Verify concurrent mutations do not crash NetworkX (RT-18)."""
    engine = InMemoryGraphEngine()

    def worker(worker_id):
        for i in range(100):
            node = GraphNode(
                semantic_hash=f"hash_{worker_id}_{i}",
                kind=NodeKind.FILE,
                name=f"file_{i}",
                file_id=f"path_{worker_id}_{i}.py",
            )
            engine.upsert_node(node)

    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(engine._nx_graph.nodes) == 1000


def test_extract_subgraph_is_not_capped():
    """A-SENS-02 FR-1: no fixed depth; RT-27's cap of 5 is gone."""
    engine = InMemoryGraphEngine()

    # Create a line graph of 10 nodes: 0 -> 1 -> ... -> 9
    for i in range(10):
        engine.upsert_node(
            GraphNode(
                semantic_hash=f"node_{i}",
                kind=NodeKind.PROCEDURE,
                name=f"proc_{i}",
                file_id="test.py",
            )
        )
        if i > 0:
            engine.upsert_edge(
                GraphEdge(source_hash=f"node_{i - 1}", target_hash=f"node_{i}", kind=EdgeKind.CALLS)
            )

    subgraph = engine.extract_subgraph("node_0", 10)

    assert set(subgraph.nodes) == {f"node_{i}" for i in range(10)}


def test_clear_cache():
    """Verify RT-13 cache clearing."""
    engine = InMemoryGraphEngine()
    engine.upsert_node(
        GraphNode(semantic_hash="test", kind=NodeKind.FILE, name="test", file_id="test.py")
    )
    assert len(engine._nx_graph.nodes) == 1
    engine.clear_cache()
    assert len(engine._nx_graph.nodes) == 0
    assert len(engine._file_index) == 0


def test_extract_subgraph_node_not_found():
    """Verify NodeNotFound is raised on unknown hash (Story 1)."""
    from specweaver.graph.core.engine.protocol import NodeNotFoundError

    engine = InMemoryGraphEngine()
    import pytest

    with pytest.raises(NodeNotFoundError):
        engine.extract_subgraph("nonexistent_hash", 2)


def test_extract_subgraph_rejects_int_ids():
    """Verify legacy integer IDs are rejected safely (Story 3)."""
    engine = InMemoryGraphEngine()
    import pytest

    with pytest.raises(ValueError, match="requires a string hash"):
        engine.extract_subgraph(123, 2)  # type: ignore
