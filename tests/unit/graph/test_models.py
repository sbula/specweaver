from specweaver.graph.models import GranularityLevel, GraphNode, NodeType


def test_graphnode_to_dict_serializes_enum_values():
    """Story 1: GraphNode.to_dict() correctly serializes enum values to strings."""
    node = GraphNode(
        id=1,
        semantic_hash="FILE:test.py",
        node_type=NodeType.FILE,
        granularity=GranularityLevel.SYSTEM,
        name="test.py",
        file_id="test.py"
    )
    data = node.to_dict()
    assert data["node_type"] == "FILE"
    assert data["granularity"] == "SYSTEM"
    assert data["is_partial"] is False
    assert data["semantic_hash"] == "FILE:test.py"
