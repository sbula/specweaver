from unittest.mock import MagicMock

import pytest

from specweaver.graph.engine import InMemoryGraphEngine
from specweaver.graph.export import generate_graphml_payload
from specweaver.graph.ontology import OntologyMapper
from specweaver.workspace.parsers.interfaces import CodeStructureInterface


def test_export_empty_graph():
    """Story 1: [Boundary] Export completely empty graph."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    engine = InMemoryGraphEngine(OntologyMapper(mock_parser))

    payload = generate_graphml_payload(engine)
    assert "<graphml" in payload
    assert "</graphml>" in payload

def test_export_strips_prompt_injection():
    """Story 15: [Hostile] Strip <|im_start|> prompt injection from metadata."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    # The parser finds a malicious class name
    mock_parser.list_symbols.return_value = ["MaliciousClass<|im_start|>"]
    mock_parser.extract_imports.return_value = []

    engine = InMemoryGraphEngine(OntologyMapper(mock_parser))
    engine.ingest_file("test.py", "class MaliciousClass<|im_start|>: pass")

    payload = generate_graphml_payload(engine)
    assert "<|im_start|>" not in payload
    assert "MaliciousClass" in payload

def test_export_path_traversal_validation():
    """Story 13: [Hostile] export_graph throws ValueError on path traversal."""

    from specweaver.graph.export import export_to_graphml

    engine = InMemoryGraphEngine(MagicMock())
    # Should throw ValueError when trying to write outside workspace
    with pytest.raises(ValueError, match="Path traversal"):
        export_to_graphml(engine, "../../../etc/passwd", "/workspace")
