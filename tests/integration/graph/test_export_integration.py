from unittest.mock import MagicMock

from specweaver.graph.engine import InMemoryGraphEngine
from specweaver.graph.export import generate_graphml_payload
from specweaver.graph.ontology import OntologyMapper
from specweaver.workspace.parsers.interfaces import CodeStructureInterface


def test_export_integration_generates_valid_graphml():
    """Story 15: GraphML Serialization Pipeline."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.list_symbols.return_value = ["TestClass"]
    mock_parser.extract_imports.return_value = []

    mapper = OntologyMapper(mock_parser)
    engine = InMemoryGraphEngine(mapper)

    engine.ingest_file("test_export.py", "class TestClass: pass")

    # Generate the payload
    payload = generate_graphml_payload(engine)

    # Verify the XML string contains expected GraphML tags and our data
    assert '<graphml' in payload
    assert 'TestClass' in payload
    assert 'test_export.py' in payload
