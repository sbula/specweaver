# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The real extractor's output actually builds a graph.

Proves: INT-US-10 FR-1

`D-SENS-02`/`D-SENS-03` emit an AST dict; `B-SENS-02`'s `OntologyMapper` consumes one. Both shipped,
and until now **nothing drove one into the other**:

* `test_graph_adapter.py` proves the adapter alone, with a real parser and a real file.
* `test_builder_integration.py` proves the builder alone, with `fake_java_parser` — a stub whose own
  docstring says it *"Simulates a Tree-Sitter AST extractor purely for integration testing delta
  logic"*.
* `test_orchestrator.py::test_orchestrator_build_target_happy_path` names the composition and then
  `MagicMock`s the repository, topology and engine, asserting `persist_semantic_digraph` was *called*.

Three green parts and no proof that the shapes agree. That is the rule the 2026-08-16 handover
recorded from four defects of the same shape: **if two things are only ever used together, test the
pair.** `ADR-004` puts a seam between two closed capabilities on the (sub)story contract, because
`finished-stories-immutable` bars either capability from accepting it.

Nothing here is mocked. Real parsers, real `OntologyMapper`, real SQLite on disk.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from specweaver.graph.core.builder.orchestrator import GraphOrchestrator
from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

PYTHON_SOURCE = '''
class OrderService:
    """A class the extractor must report."""

    def submit(self) -> None:
        pass


def module_level_helper() -> int:
    return 1
'''


def _project(root: Path, files: dict[str, str]) -> Path:
    """A real project tree with a `.specweaver/` directory, as `build_target` expects."""
    (root / ".specweaver").mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def _nodes(db: Path) -> list[tuple[str, str]]:
    """`(name, semantic_hash)` for every active node the run persisted."""
    with sqlite3.connect(db) as conn:
        return [
            (name, semantic_hash)
            for semantic_hash, name in conn.execute(
                "SELECT semantic_hash, service_name FROM graph_nodes WHERE is_active = 1"
            )
        ]


def test_the_adapter_and_the_mapper_agree_on_the_ast_shape(tmp_path: Path) -> None:
    """The narrow claim, stated without SQLite in the way.

    A shape mismatch here is invisible to both sides' own tests: the adapter would still return a
    dict and the mapper would still return its FILE node, so each suite stays green while the graph
    silently contains nothing but files.
    """
    project = _project(tmp_path, {"src/orders.py": PYTHON_SOURCE})
    ast_data = extract_ast_dict(str(project / "src" / "orders.py"))

    names = {child["name"] for child in ast_data["children"]}
    assert "OrderService" in names, f"real extractor reported no class: {ast_data}"
    assert "module_level_helper" in names, f"real extractor reported no function: {ast_data}"
    assert {child["type"] for child in ast_data["children"]} <= {
        "class_definition",
        "function_definition",
    }, "the mapper only maps these two node types"


def test_a_real_build_persists_symbols_the_extractor_found(tmp_path: Path) -> None:
    """End to end: real parser -> real mapper -> real SQLite, nothing mocked.

    Asserts the graph holds MORE than the FILE node the mapper always emits. That is the assertion a
    shape mismatch fails, and the one every existing test omits.
    """
    project = _project(tmp_path, {"src/orders.py": PYTHON_SOURCE})

    count = GraphOrchestrator.build_target(project / "src" / "orders.py", project)
    assert count >= 1, "build_target reported no files processed"

    db = project / ".specweaver" / "graph.db"
    assert db.is_file(), "no graph database was written"

    persisted = _nodes(db)
    assert len(persisted) > 1, (
        "only the FILE node was persisted, so the extractor's symbols never reached the mapper: "
        f"{persisted}"
    )


def test_a_second_build_does_not_duplicate_nodes(tmp_path: Path) -> None:
    """Dedup across the real composition, not only inside the repository's own tests.

    `B-SENS-02` FR-2 promises exact structural duplicates merge to one node id. Its unit tests prove
    the constraint; this proves the hashes the real extractor produces are stable enough to hit it.
    """
    project = _project(tmp_path, {"src/orders.py": PYTHON_SOURCE})
    target = project / "src" / "orders.py"

    GraphOrchestrator.build_target(target, project)
    first = _nodes(project / ".specweaver" / "graph.db")

    GraphOrchestrator.build_target(target, project)
    second = _nodes(project / ".specweaver" / "graph.db")

    assert len(second) == len(first), f"a re-build duplicated nodes: {len(first)} -> {len(second)}"


@pytest.mark.xfail(
    strict=True,
    reason="blocked on TECH-061 — GraphOrchestrator.collect_files filters .py only",
)
def test_a_non_python_source_also_reaches_the_graph(tmp_path: Path) -> None:
    """The polyglot half of the claim — `D-SENS-03`'s extractors, not just Python.

    **Currently xfail(strict=True) against `TECH-061`.** `collect_files` accepts `.py` and nothing
    else (`orchestrator.py:85-97`), so a Java file is dropped before the mapper is reached and the
    run persists zero nodes — not even the FILE node. This test found that on its first run, which
    is exactly what `ADR-004` clause 4 writes tests early for.

    `strict=True` means closing `TECH-061` turns this into a failure until the marker is removed, and
    `check_xfail_blockers.py` fails the `doc` gate if it is left behind.

    **No grammar skip.** A first draft skipped when the Java grammar was unavailable; R8 in
    `check_conventions.py` rejected it, and correctly — `tree-sitter-java` is a hard dependency in
    `pyproject.toml`, so the grammar is something this repo CONTROLS. Skipping on it would convert a
    defect into a green run, which is the whole point of that rule. The branch was dead in any case:
    the extractor does report the class, and the run still persists nothing.
    """
    java = "public class UserService {\n    public void register() {}\n}\n"
    project = _project(tmp_path, {"src/UserService.java": java})
    source = project / "src" / "UserService.java"

    ast_data = extract_ast_dict(str(source))
    assert ast_data["children"], "the shipped Java extractor reported no symbols at all"

    GraphOrchestrator.build_target(source, project)
    persisted = _nodes(project / ".specweaver" / "graph.db")
    assert len(persisted) > 1, f"Java symbols did not reach the graph: {persisted}"
