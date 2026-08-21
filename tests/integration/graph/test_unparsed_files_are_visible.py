# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A file the build could not read is marked, so an absent edge is not mistaken for no edge.

Proves: TECH-068 FR-15

`extract_ast_dict` catches, logs a warning and returns an empty tree. A warning is invisible to a
graph reader, and across thousands of files it is unreadable to a human too — so a file nobody could
open looked exactly like a file with nothing in it. That is the silent-empty result this whole
ticket exists to remove: a traversal returning nothing must not have two meanings.

Only a genuine failure is marked. `collect_files` filters to parseable suffixes, so "no parser"
cannot arise on the normal path, and a skipped symlink is a deliberate exclusion rather than a
failure. What remains is a file that could not be read and a parser that raised.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.hashing import SemanticHasher
from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _file_node_metadata(engine: InMemoryGraphEngine, path: str) -> dict[str, Any]:
    graph = engine.export_semantic_digraph()
    return dict(graph.nodes[SemanticHasher().hash_file(path)].get("metadata") or {})


def _ingest(path: str) -> InMemoryGraphEngine:
    engine = InMemoryGraphEngine()
    GraphBuilder(engine=engine, parser=extract_ast_dict).ingest_file(path)
    return engine


def test_a_readable_file_is_not_marked(tmp_path: Path) -> None:
    """Happy path: the marker means something only if it is absent when nothing went wrong."""
    path = tmp_path / "ok.py"
    path.write_text("def f():\n    pass\n", encoding="utf-8")
    assert "unparsed" not in _file_node_metadata(_ingest(str(path)), str(path))


def test_an_empty_file_is_parsed_not_unparsed(tmp_path: Path) -> None:
    """Boundary: nothing in it is not the same as could not read it."""
    path = tmp_path / "empty.py"
    path.write_text("", encoding="utf-8")
    assert "unparsed" not in _file_node_metadata(_ingest(str(path)), str(path))


def test_a_file_that_cannot_be_read_is_marked(tmp_path: Path) -> None:
    """Graceful degradation: a directory wearing a source file's name cannot be read as text."""
    path = tmp_path / "trap.py"
    path.mkdir()
    assert _file_node_metadata(_ingest(str(path)), str(path))["unparsed"] == "read"


def test_a_parser_that_raises_marks_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hostile: a grammar that blows up must leave a record, not a silent hole."""
    path = tmp_path / "boom.py"
    path.write_text("def f(): pass\n", encoding="utf-8")

    class Exploding:
        def list_symbols(self, code: str) -> list[str]:
            raise RuntimeError("grammar exploded")

    monkeypatch.setattr(
        "specweaver.workspace.ast.adapters.graph_adapter.get_default_parsers",
        lambda: {(".py",): Exploding()},
    )
    assert _file_node_metadata(_ingest(str(path)), str(path))["unparsed"] == "parse"


def test_the_seam_reports_the_failure_itself(tmp_path: Path) -> None:
    """The adapter is where the failure is known, so it is where the fact must originate."""
    path = tmp_path / "trap.py"
    path.mkdir()
    assert extract_ast_dict(str(path))["unparsed"] == "read"
