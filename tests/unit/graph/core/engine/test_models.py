import pytest
from pydantic import ValidationError

from specweaver.graph.core.engine.models import GraphEdge, GraphNode
from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind


def test_graph_node_normalize_file_id():
    """Test RT-21: Case-insensitive path normalization."""
    node = GraphNode(
        semantic_hash="hash123",
        kind=NodeKind.FILE,
        name="test",
        file_id="C:\\Windows\\Path\\File.PY"
    )
    assert node.file_id == "c:/windows/path/file.py"

def test_graph_node_metadata_limit():
    """Test RT-25: Metadata 2KB limit enforcement."""
    # Under limit should pass
    node = GraphNode(
        semantic_hash="hash123",
        kind=NodeKind.PROCEDURE,
        name="test_func",
        file_id="test.py",
        metadata={"key": "small value"}
    )
    assert node.metadata["key"] == "small value"

    # Over limit should fail (create a payload > 2KB)
    large_payload = "A" * 2500
    with pytest.raises(ValidationError) as exc:
        GraphNode(
            semantic_hash="hash123",
            kind=NodeKind.PROCEDURE,
            name="test_func",
            file_id="test.py",
            metadata={"key": large_payload}
        )
    assert "exceeds 2KB limit" in str(exc.value)

def test_graph_edge_creation():
    """Test basic GraphEdge initialization."""
    edge = GraphEdge(
        source_hash="src123",
        target_hash="tgt456",
        kind=EdgeKind.CALLS
    )
    assert edge.source_hash == "src123"
    assert edge.target_hash == "tgt456"
    assert edge.kind == EdgeKind.CALLS
