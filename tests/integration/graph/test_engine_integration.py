from unittest.mock import MagicMock

from specweaver.graph.engine import InMemoryGraphEngine
from specweaver.graph.ontology import OntologyMapper
from specweaver.workspace.parsers.interfaces import CodeStructureInterface


def test_integration_ingest_and_query():
    """Story 14: Mock Parser -> Ontology -> Engine -> Subgraph query."""
    # Mock the parser to return some fake symbols
    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.list_symbols.return_value = ["MyClass"]
    mock_parser.extract_imports.return_value = ["os"]

    mapper = OntologyMapper(mock_parser)
    engine = InMemoryGraphEngine(mapper)

    engine.ingest_file("test.py", "import os\nclass MyClass: pass")

    # Verify nodes were mapped and inserted
    file_id = engine._hash_to_id["FILE:test.py"]
    class_id = engine._hash_to_id["CLASS:test.py:MyClass"]

    assert engine._graph.has_node(file_id)
    assert engine._graph.has_node(class_id)
    assert engine._graph.number_of_edges() == 1  # The lazy import edge
