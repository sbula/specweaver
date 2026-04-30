from unittest.mock import MagicMock

import pytest

from specweaver.graph.engine import InMemoryGraphEngine
from specweaver.graph.models import GranularityLevel, GraphNode, NodeType
from specweaver.graph.ontology import OntologyMapper


@pytest.fixture
def engine():
    mock_mapper = MagicMock(spec=OntologyMapper)
    # Default mock returns
    mock_mapper.map_file_to_nodes.return_value = []
    mock_mapper.map_file_to_edges.return_value = []
    return InMemoryGraphEngine(mock_mapper)

def test_get_or_create_id_increments_uniquely(engine):
    """Story 6: _get_or_create_id increments internal ID counter uniquely."""
    id1 = engine._get_or_create_id("hash1")
    id2 = engine._get_or_create_id("hash2")
    id3 = engine._get_or_create_id("hash1")

    assert id1 == 1
    assert id2 == 2
    assert id3 == 1  # Re-uses hash1

def test_ingest_file_ignores_large_files(engine):
    """Story 8: ingest_file ignores file when code exceeds 1MB threshold."""
    large_code = "a" * (1024 * 1024 + 1)
    engine.ingest_file("large.py", large_code)

    engine._ontology.map_file_to_nodes.assert_not_called()

def test_ingest_file_hard_resets_prior_nodes(engine):
    """Story 9: ingest_file hard resets (removes) prior nodes if file is re-ingested."""
    node1 = GraphNode(id=-1, semantic_hash="hash1", node_type=NodeType.FILE, granularity=GranularityLevel.SYSTEM, name="file1.py", file_id="file1.py")
    node2 = GraphNode(id=-1, semantic_hash="hash2", node_type=NodeType.FILE, granularity=GranularityLevel.SYSTEM, name="file1.py", file_id="file1.py")

    # First ingest
    engine._ontology.map_file_to_nodes.return_value = [node1]
    engine.ingest_file("file1.py", "code1")
    assert engine._graph.number_of_nodes() == 1

    # Second ingest (should replace)
    engine._ontology.map_file_to_nodes.return_value = [node2]
    engine.ingest_file("file1.py", "code2")
    assert engine._graph.number_of_nodes() == 1

    # Verify the new node is in the graph, and old one is gone
    nodes = list(engine._graph.nodes(data=True))
    assert nodes[0][1]["semantic_hash"] == "hash2"

def test_query_subgraph_microservice_firewall(engine):
    """Story 10 & 11: query_subgraph drops foreign APPLICATION/IMPLEMENTATION, retains SYSTEM."""
    # Build a fake graph manually
    id1 = engine._get_or_create_id("FILE:local/ns1.py")
    id2 = engine._get_or_create_id("FILE:foreign/ns2.py")
    id3 = engine._get_or_create_id("CLASS:foreign/ns2.py:MyClass")

    # Local System node
    engine._graph.add_node(id1, granularity=GranularityLevel.SYSTEM.value, file_id="local/ns1.py")
    # Foreign System node
    engine._graph.add_node(id2, granularity=GranularityLevel.SYSTEM.value, file_id="foreign/ns2.py")
    # Foreign Application node
    engine._graph.add_node(id3, granularity=GranularityLevel.APPLICATION.value, file_id="foreign/ns2.py")

    # Connect them so they are in the subgraph
    engine._graph.add_edge(id1, id2)
    engine._graph.add_edge(id2, id3)

    # Query with whitelist
    subgraph = engine.query_subgraph(id1, depth=3, whitelist_namespaces=["local/"])

    # Should contain local SYSTEM and foreign SYSTEM, but drop foreign APPLICATION
    assert subgraph.has_node(id1)
    assert subgraph.has_node(id2)
    assert not subgraph.has_node(id3)

def test_clear_cache(engine):
    """Story 12: clear_cache wipes NetworkX and internal dictionaries."""
    engine._get_or_create_id("hash")
    engine._graph.add_node(1)
    engine._file_to_node_ids["file"] = [1]

    engine.clear_cache()

    assert engine._graph.number_of_nodes() == 0
    assert engine._next_id == 1
    assert len(engine._hash_to_id) == 0
    assert len(engine._file_to_node_ids) == 0
