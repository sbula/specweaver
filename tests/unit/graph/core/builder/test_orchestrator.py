# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

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

    # v1 declares three functions; v2 drops `baz`, so `baz`'s containment edge must be deleted.
    #
    # The original fixture instead gave `foo` a `"calls": ["bar"]` key and removed it in v2 —
    # but NOTHING in `src/specweaver/graph/` reads `calls`. The mapper builds edges from
    # `children` only, so no call edge was ever created and the deletion path was never entered:
    # both versions produced the same two module->function edges. Paired with an
    # `assert len(edges) >= 0` that cannot fail, this test proved nothing about Story 4 for its
    # entire life. Vacuous-proof pattern 4 — the fixture could not satisfy the assertion.
    ast_data_v1 = {
        "type": "module",
        "children": [
            {"type": "function_definition", "name": "foo"},
            {"type": "function_definition", "name": "bar"},
            {"type": "function_definition", "name": "baz"},
        ],
    }
    builder.ingest_ast("src/test.py", ast_data_v1)

    edges_v1 = set(engine._nx_graph.edges)
    assert len(edges_v1) == 3, f"expected one edge per function, got {sorted(edges_v1)}"

    ast_data_v2 = {
        "type": "module",
        "children": [
            {"type": "function_definition", "name": "foo"},
            {"type": "function_definition", "name": "bar"},
        ],
    }
    builder.ingest_ast("src/test.py", ast_data_v2)

    # A strict subset, not an absolute count: foo and bar are still legitimately contained, so
    # exactly one edge — baz's — may disappear.
    #
    # This asserts the observable graph state, NOT which internal mechanism produced it. Verified
    # by probe: `ingest_ast` prunes stale edges twice over — step 1 (`edges_to_remove`) and step 2
    # (`remove_node`, which cascades in NetworkX) — and disabling either alone still satisfies
    # this test. That redundancy means **step 1 is currently exercised by no test**: with the
    # mapper producing only parent->child containment edges, an edge can never disappear while
    # both endpoints survive, which is the only case step 1 uniquely handles. It would become
    # reachable if the mapper ever emits non-containment edges (calls, imports).
    edges_v2 = set(engine._nx_graph.edges)

    assert edges_v2 < edges_v1, (
        f"re-ingest deleted no edges; before={sorted(edges_v1)} after={sorted(edges_v2)}"
    )
    assert len(edges_v2) == 2, f"expected baz's edge gone and no others, got {sorted(edges_v2)}"


def test_orchestrator_build_target_happy_path(tmp_path):
    from unittest.mock import MagicMock, patch

    import networkx as nx

    from specweaver.graph.core.builder.orchestrator import GraphOrchestrator

    mock_topology = MagicMock()
    mock_node = MagicMock()
    mock_node.name = "my_service"
    mock_node.yaml_path = tmp_path / "context.yaml"
    mock_topology.nodes = {"my_service": mock_node}

    mock_repo = MagicMock()
    mock_repo.load_from_db.return_value = nx.DiGraph()

    with (
        patch("specweaver.assurance.graph.loader.load_topology", return_value=mock_topology),
        patch(
            "specweaver.graph.core.store.repository.SqliteGraphRepository", return_value=mock_repo
        ),
        patch("specweaver.graph.core.builder.orchestrator.GraphBuilder") as mock_builder_class,
    ):
        mock_builder = MagicMock()
        mock_builder.collect_files.return_value = {"file1.py"}
        mock_builder.ingest_target.return_value = 1
        mock_builder_class.return_value = mock_builder

        count = GraphOrchestrator.build_target(tmp_path / "file1.py", tmp_path)
        assert count == 1
        mock_repo.purge_stale_entries.assert_called_once_with({"file1.py"})
        mock_repo.load_from_db.assert_called_once()
        mock_repo.persist_semantic_digraph.assert_called_once()


def test_orchestrator_build_target_fallback(tmp_path):
    from unittest.mock import MagicMock, patch

    import networkx as nx

    from specweaver.graph.core.builder.orchestrator import GraphOrchestrator

    mock_repo = MagicMock()
    mock_repo.load_from_db.return_value = nx.DiGraph()

    with (
        patch("specweaver.assurance.graph.loader.load_topology", return_value=None),
        patch(
            "specweaver.graph.core.store.repository.SqliteGraphRepository", return_value=mock_repo
        ) as mock_repo_class,
        patch("specweaver.graph.core.builder.orchestrator.GraphBuilder") as mock_builder_class,
    ):
        mock_builder = MagicMock()
        mock_builder.collect_files.return_value = set()
        mock_builder.ingest_target.return_value = 0
        mock_builder_class.return_value = mock_builder

        count = GraphOrchestrator.build_target(tmp_path, tmp_path)
        assert count == 0
        mock_repo_class.assert_called_once_with(
            str(tmp_path / ".specweaver" / "graph.db"), "default"
        )
