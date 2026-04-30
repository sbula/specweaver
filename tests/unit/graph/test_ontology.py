from unittest.mock import MagicMock

import pytest

from specweaver.graph.models import GranularityLevel, NodeType
from specweaver.graph.ontology import OntologyMapper
from specweaver.workspace.parsers.interfaces import CodeStructureInterface


@pytest.fixture
def mock_parser():
    return MagicMock(spec=CodeStructureInterface)

def test_map_file_to_nodes_creates_file_node_on_parser_failure(mock_parser):
    """Story 2 & 3: Creates FILE node and flags is_partial=True on parser failure."""
    mock_parser.list_symbols.side_effect = Exception("Parse error")
    mapper = OntologyMapper(mock_parser)

    nodes = mapper.map_file_to_nodes("test.py", "invalid code")

    assert len(nodes) == 1
    assert nodes[0].node_type == NodeType.FILE
    assert nodes[0].is_partial is True
    assert nodes[0].semantic_hash == "FILE:test.py"

def test_map_file_to_nodes_assigns_class_and_application_granularity(mock_parser):
    """Story 4: Assigns CLASS/APPLICATION to uppercase symbols, PROCEDURE/IMPLEMENTATION to lowercase."""
    mock_parser.list_symbols.return_value = ["MyClass", "my_function"]
    mapper = OntologyMapper(mock_parser)

    nodes = mapper.map_file_to_nodes("test.py", "code")

    # 1 File node + 2 symbol nodes = 3 total
    assert len(nodes) == 3

    class_node = next(n for n in nodes if n.name == "MyClass")
    func_node = next(n for n in nodes if n.name == "my_function")

    assert class_node.node_type == NodeType.CLASS
    assert class_node.granularity == GranularityLevel.APPLICATION

    assert func_node.node_type == NodeType.PROCEDURE
    assert func_node.granularity == GranularityLevel.IMPLEMENTATION

def test_map_file_to_edges_gracefully_returns_empty_list_on_failure(mock_parser):
    """Story 5: map_file_to_edges gracefully returns empty list on parser exception."""
    mock_parser.extract_imports.side_effect = Exception("Parse error")
    mapper = OntologyMapper(mock_parser)

    edges = mapper.map_file_to_edges("test.py", "invalid code")
    assert edges == []

def test_map_file_to_edges_returns_lazy_edges(mock_parser):
    """Validates edges are correctly mapped from imports."""
    mock_parser.extract_imports.return_value = ["os", "sys"]
    mapper = OntologyMapper(mock_parser)

    edges = mapper.map_file_to_edges("test.py", "code")

    assert len(edges) == 2
    assert edges[0].edge_type == "IMPORTS"
    assert edges[0].metadata["target_name"] == "os"
    assert edges[0].target_id == -1  # Dangling/lazy
