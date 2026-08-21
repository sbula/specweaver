# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every type is known before any edge is built, and every file is parsed once.

Proves: TECH-068 FR-4

`FR-8` resolved imports against PATHS, which `collect_files` knows before reading anything. A
supertype names a SYMBOL, and symbols are only known after parsing. Resolving against whatever the
build has accumulated so far would make the answer depend on ingestion order — and that order is not
deterministic: `collect_files` returns a `set` and `ingest_target` iterates it, so the same tree
would build a different graph on different runs. That is not a weaker guarantee, it is none.

So the index is built in a prepass, before any edge is emitted. `FR-11` in `SF-04` needs the same
thing, which is why `SF-04`'s dependency moved from `SF-02` to here.

The prepass must not cost a second parse. Measured 2.8 ms/file; parsing twice takes the reference
workload's 3,000 files to roughly 17 s against `NFR-1`'s 60 s budget for everything this ticket adds.
The prepass keeps what it read and ingest reuses it.

The tier is integration: determinism across a whole build is not a claim one module can make.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine

if TYPE_CHECKING:
    from pathlib import Path


class _CountingParser:
    """Reports the types each file declares, and remembers how often it was asked."""

    def __init__(self, types: dict[str, list[str]]) -> None:
        self.types = types
        self.calls: list[str] = []

    def __call__(self, filepath: str) -> dict[str, Any]:
        self.calls.append(filepath)
        return {
            "type": "module",
            "imports": [],
            "children": [
                {"type": "class_definition", "name": name, "supertypes": [], "calls": []}
                for name in self.types.get(filepath, [])
            ],
        }


def _tree(tmp_path: Path, types: dict[str, list[str]]) -> tuple[GraphBuilder, _CountingParser]:
    absolute = {}
    for rel, names in types.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        absolute[str(path)] = names
    parser = _CountingParser(absolute)
    return GraphBuilder(engine=InMemoryGraphEngine(), parser=parser), parser


def test_a_type_is_indexed_to_the_file_that_declares_it(tmp_path: Path) -> None:
    """Happy path."""
    builder, _ = _tree(tmp_path, {"a.py": ["Base"], "b.py": []})
    builder.ingest_target(tmp_path)
    assert builder.symbol_index["Base"] == {str(tmp_path / "a.py")}


def test_a_type_declared_in_a_file_ingested_later_is_still_known(tmp_path: Path) -> None:
    """Hostile: the property an order-dependent index cannot have.

    `zzz.py` sorts last however the build walks the tree, so a resolver consulting only what has
    been ingested so far would not find `Base` while `aaa.py` is being processed.
    """
    builder, _ = _tree(tmp_path, {"aaa.py": ["Impl"], "zzz.py": ["Base"]})
    builder.ingest_target(tmp_path)
    assert builder.symbol_index["Base"] == {str(tmp_path / "zzz.py")}


def test_a_name_declared_twice_maps_to_both_files(tmp_path: Path) -> None:
    """Boundary: two classes named `Config` are not one class, and CB-4 needs to see that."""
    builder, _ = _tree(tmp_path, {"one.py": ["Config"], "two.py": ["Config"]})
    builder.ingest_target(tmp_path)
    assert builder.symbol_index["Config"] == {str(tmp_path / "one.py"), str(tmp_path / "two.py")}


def test_every_file_is_parsed_exactly_once(tmp_path: Path) -> None:
    """The prepass keeps what it read; a second parse would double the cost NFR-1 budgets for."""
    builder, parser = _tree(tmp_path, {"a.py": ["Base"], "b.py": ["Impl"], "c.py": []})
    builder.ingest_target(tmp_path)
    assert sorted(parser.calls) == sorted(set(parser.calls))
    assert len(parser.calls) == 3


def test_a_tree_with_no_types_has_an_empty_index(tmp_path: Path) -> None:
    """Boundary: empty is a real state, not a missing attribute."""
    builder, _ = _tree(tmp_path, {"a.py": [], "b.py": []})
    builder.ingest_target(tmp_path)
    assert builder.symbol_index == {}


def test_two_builds_of_one_tree_agree(tmp_path: Path) -> None:
    """Graceful degradation: the same tree must not build two different graphs."""
    builder_one, _ = _tree(tmp_path, {"a.py": ["Impl"], "b.py": ["Base"]})
    builder_one.ingest_target(tmp_path)
    builder_two, _ = _tree(tmp_path, {"a.py": ["Impl"], "b.py": ["Base"]})
    builder_two.ingest_target(tmp_path)
    assert builder_one.symbol_index == builder_two.symbol_index


def test_the_index_is_complete_while_files_are_being_ingested(tmp_path: Path) -> None:
    """The ordering IS the requirement, so it is observed during the loop, not after it.

    Building the index after ingesting would leave every assertion above green while the property
    the prepass exists for — that a supertype resolves the same whichever file the build reaches
    first — is absent. `SF-04`'s resolver consults this mid-ingest; nothing here would notice it
    was empty.
    """
    builder, _ = _tree(tmp_path, {"aaa.py": ["Impl"], "zzz.py": ["Base"]})
    seen: list[set[str]] = []
    original = builder.ingest_ast

    def spy(filepath: str, ast_data: dict[str, Any]) -> None:
        seen.append(set(builder.symbol_index))
        original(filepath, ast_data)

    builder.ingest_ast = spy  # type: ignore[method-assign]
    builder.ingest_target(tmp_path)

    assert seen, "nothing was ingested, so the ordering was never observed"
    assert all(names == {"Impl", "Base"} for names in seen)
