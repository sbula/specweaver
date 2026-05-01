import threading

import pytest

from specweaver.graph.engine.core import InMemoryGraphEngine
from specweaver.graph.engine.models import GraphEdge, GraphNode
from specweaver.graph.engine.ontology import EdgeKind, NodeKind


def test_engine_thread_safety():
    """Verify concurrent mutations do not crash NetworkX (RT-18)."""
    engine = InMemoryGraphEngine()

    def worker(worker_id):
        for i in range(100):
            node = GraphNode(
                semantic_hash=f"hash_{worker_id}_{i}",
                kind=NodeKind.FILE,
                name=f"file_{i}",
                file_id=f"path_{worker_id}_{i}.py"
            )
            engine.upsert_node(node)

    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(engine._graph.nodes) == 1000

@pytest.mark.asyncio
async def test_extract_subgraph_max_depth():
    """Verify max depth restriction for subgraph extraction (RT-27)."""
    engine = InMemoryGraphEngine()

    # Create a line graph of 10 nodes: 0 -> 1 -> ... -> 9
    for i in range(10):
        engine.upsert_node(GraphNode(
            semantic_hash=f"node_{i}",
            kind=NodeKind.PROCEDURE,
            name=f"proc_{i}",
            file_id="test.py"
        ))
        if i > 0:
            engine.upsert_edge(GraphEdge(
                source_hash=f"node_{i-1}",
                target_hash=f"node_{i}",
                kind=EdgeKind.CALLS
            ))

    # Extract from node_0 with depth 10. Max depth is hard-coded to 5.
    # Therefore, it should return nodes 0, 1, 2, 3, 4, 5 (total 6 nodes)
    subgraph = await engine.extract_subgraph("node_0", 10)

    assert len(subgraph.nodes) == 6
    assert "node_0" in subgraph.nodes
    assert "node_5" in subgraph.nodes
    assert "node_6" not in subgraph.nodes

def test_clear_cache():
    """Verify RT-13 cache clearing."""
    engine = InMemoryGraphEngine()
    engine.upsert_node(GraphNode(
        semantic_hash="test",
        kind=NodeKind.FILE,
        name="test",
        file_id="test.py"
    ))
    assert len(engine._graph.nodes) == 1
    engine.clear_cache()
    assert len(engine._graph.nodes) == 0
    assert len(engine._hash_to_int) == 0
