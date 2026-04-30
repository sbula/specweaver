import threading
from unittest.mock import MagicMock

from specweaver.graph.engine import InMemoryGraphEngine
from specweaver.graph.ontology import OntologyMapper
from specweaver.workspace.parsers.interfaces import CodeStructureInterface


def test_engine_concurrency_poisoning():
    """Story 10: [Hostile] Two threads ingest and query simultaneously."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.list_symbols.return_value = ["ConcurrentClass"]
    mock_parser.extract_imports.return_value = []

    engine = InMemoryGraphEngine(OntologyMapper(mock_parser))

    # We will run 10 threads doing ingests and queries simultaneously
    exceptions = []
    def worker(i):
        try:
            engine.ingest_file(f"test_{i}.py", "code")
            engine.query_subgraph(1)
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(exceptions) == 0, f"Concurrency errors occurred: {exceptions}"

def test_engine_tombstone_edge_cleanup():
    """Story 11: [Boundary] Purged nodes must sever all edges."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.list_symbols.return_value = ["OldClass"]
    engine = InMemoryGraphEngine(OntologyMapper(mock_parser))

    engine.ingest_file("file_a.py", "code")
    old_id = engine._hash_to_id["FILE:file_a.py"]

    # Manually add a fake edge to simulate connectivity
    engine._graph.add_edge(old_id, 999)
    assert engine._graph.number_of_edges() == 1

    # Re-ingest the file
    engine.ingest_file("file_a.py", "code")

    # The old node should be deleted, and its edges purged
    assert not engine._graph.has_edge(old_id, 999)

def test_engine_atomicity_on_parser_exception():
    """Story 12: [Degradation] Parser crash mid-ingestion rolls back."""
    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.map_file_to_nodes = MagicMock(side_effect=Exception("Parser crashed"))

    engine = InMemoryGraphEngine(mock_parser)

    import contextlib
    with contextlib.suppress(Exception):
        engine.ingest_file("crash.py", "code")

    assert engine._graph.number_of_nodes() == 0
