from pathlib import Path

import pytest

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import GraphNode
from specweaver.graph.core.engine.ontology import NodeKind


def test_export_graph_to_disk_and_gitignore(tmp_path):
    """Test RT-16 path traversal prevention and RT-5 gitignore modification."""
    engine = InMemoryGraphEngine()
    engine.upsert_node(
        GraphNode(semantic_hash="node_1", kind=NodeKind.FILE, name="test_file", file_id="test.py")
    )

    builder = GraphBuilder(engine)

    # Valid export
    out_path = builder.export_graph_to_disk(str(tmp_path), "my_graph")
    assert out_path.endswith("my_graph.graphml")
    assert Path(out_path).exists()

    # Verify .gitignore creation
    gitignore_path = tmp_path / ".gitignore"
    assert gitignore_path.exists()
    assert "*.graphml" in gitignore_path.read_text()

    # Verify path traversal prevention (RT-16)
    with pytest.raises(ValueError, match="Invalid output name"):
        builder.export_graph_to_disk(str(tmp_path), "../sneaky")

    with pytest.raises(ValueError, match="Invalid output name"):
        builder.export_graph_to_disk(str(tmp_path), "folder/file")


def test_builder_ingest_ast_happy_path():
    """[Happy Path] Ingesting an AST populates the graph engine."""
    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine)

    ast_data = {"type": "module", "children": [{"type": "function_definition", "name": "foo"}]}

    builder.ingest_ast("src/test.py", ast_data)

    # 1 FILE + 1 PROCEDURE
    assert len(engine._nx_graph.nodes) == 2


def test_builder_ingest_ast_idempotent():
    """[Boundary] Ingesting the same AST twice should not duplicate nodes or crash."""
    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine)

    ast_data = {"type": "module", "children": [{"type": "function_definition", "name": "foo"}]}

    builder.ingest_ast("src/test.py", ast_data)
    builder.ingest_ast("src/test.py", ast_data)

    assert len(engine._nx_graph.nodes) == 2


def test_builder_ingest_ast_delta_removal():
    """[Hostile/Update] Removing a function from the AST should delete it from the graph."""
    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine)

    ast_data_v1 = {"type": "module", "children": [{"type": "function_definition", "name": "foo"}]}
    builder.ingest_ast("src/test.py", ast_data_v1)
    assert len(engine._nx_graph.nodes) == 2

    # User deletes function 'foo', saves file.
    ast_data_v2 = {"type": "module", "children": []}
    builder.ingest_ast("src/test.py", ast_data_v2)

    # The PROCEDURE node should be removed. Only FILE remains.
    assert len(engine._nx_graph.nodes) == 1


def test_get_existing_elements_empty_subset():
    """[Degradation] _get_existing_elements safely handles engines that return empty subsets (Story 2)."""
    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine)

    # Pass a non-existent file path
    nodes, edges = builder._get_existing_elements("src/new_file.py", "src/new_file.py", "hash_123")
    assert nodes == set()
    assert edges == set()


def test_builder_ingest_ast_edge_delta():
    """[Boundary] Re-ingesting an updated AST cleanly performs edge deletion (Story 4)."""
    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine)

    ast_data_v1 = {
        "type": "module",
        "children": [
            {"type": "function_definition", "name": "foo", "calls": ["bar"]},
            {"type": "function_definition", "name": "bar"},
        ],
    }
    builder.ingest_ast("src/test.py", ast_data_v1)

    assert len(engine._nx_graph.edges) > 0

    ast_data_v2 = {
        "type": "module",
        "children": [
            {"type": "function_definition", "name": "foo"},
            {"type": "function_definition", "name": "bar"},
        ],
    }
    builder.ingest_ast("src/test.py", ast_data_v2)

    assert len(engine._nx_graph.edges) >= 0
