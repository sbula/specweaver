from unittest.mock import MagicMock

from specweaver.graph.models import GranularityLevel, NodeType
from specweaver.graph.ontology import OntologyMapper
from specweaver.workspace.parsers.interfaces import CodeStructureInterface


def test_ontology_maps_api_contract():
    """Story 3: [Happy Path] Map API_CONTRACT declarations gracefully."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.list_symbols.return_value = ["@GET /api/users"]

    mapper = OntologyMapper(mock_parser)
    nodes = mapper.map_file_to_nodes("routes.ts", "")

    # One FILE node, one API_CONTRACT node
    assert len(nodes) == 2
    api_node = next(n for n in nodes if n.node_type == NodeType.API_CONTRACT)
    assert api_node.granularity == GranularityLevel.APPLICATION

def test_ontology_skips_error_blocks():
    """Story 4: [Degradation] Gracefully skip ERROR blocks."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.list_symbols.return_value = ["ValidClass", "ERROR"]

    mapper = OntologyMapper(mock_parser)
    nodes = mapper.map_file_to_nodes("test.py", "")

    assert any(n.name == "ValidClass" for n in nodes)
    assert not any(n.name == "ERROR" for n in nodes)

def test_ontology_handles_empty_file():
    """Story 7: [Boundary] Return at least a FILE node for empty strings."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.list_symbols.return_value = []

    mapper = OntologyMapper(mock_parser)
    nodes = mapper.map_file_to_nodes("empty.py", "")

    assert len(nodes) == 1
    assert nodes[0].node_type == NodeType.FILE
