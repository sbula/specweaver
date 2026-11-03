# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`load_nodes` reads every manifest, its `widens` included, and writes nothing.

Proves: TECH-082 FR-15

The boundary rule reads `widens` from each manifest; a loader that dropped it would make every
declared widening look undeclared. `load_nodes` is the reading half of `from_project` without the
hashing and the inferring, so a check of a whole tree neither writes files nor hashes sources.

| Bucket | Case |
|---|---|
| Happy | a `widens` map is loaded with its reasons |
| Boundary | a manifest without `widens` loads an empty map; `from_project` loads the same nodes |
| Degradation | a `widens` list becomes entries with empty reasons, and a warning |
| Hostile | a `widens` scalar becomes an empty map, and a warning; a folder without a manifest gets none written |
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from specweaver.assurance.graph.topology import TopologyGraph, load_nodes
from specweaver.graph.topology.engine import TopologyEngine


def _manifest(folder: Path, body: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "context.yaml").write_text(body, encoding="utf-8")


def test_a_widens_map_is_loaded_with_its_reasons(tmp_path: Path) -> None:
    _manifest(
        tmp_path / "cli",
        "name: cli\narchetype: orchestrator\nconsumes: [kit]\n"
        "widens:\n  kit: the commands print through it\n",
    )

    nodes, warnings = load_nodes(tmp_path)

    assert nodes["cli"].widens == {"kit": "the commands print through it"}
    assert warnings == []


def test_a_manifest_without_widens_loads_an_empty_map(tmp_path: Path) -> None:
    _manifest(tmp_path / "core", "name: core\narchetype: pure-logic\n")

    nodes, _ = load_nodes(tmp_path)

    assert nodes["core"].widens == {}


def test_from_project_loads_the_same_nodes(tmp_path: Path) -> None:
    _manifest(tmp_path / "core", "name: core\narchetype: pure-logic\nwidens: {kit: why}\n")
    _manifest(tmp_path / "kit", "name: kit\narchetype: adapter\n")

    nodes, _ = load_nodes(tmp_path)
    graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)

    assert set(graph.nodes) == set(nodes) == {"core", "kit"}
    assert graph.nodes["core"].widens == {"kit": "why"}


def test_a_widens_list_has_empty_reasons_and_warns(tmp_path: Path) -> None:
    _manifest(tmp_path / "cli", "name: cli\nconsumes: [kit]\nwidens: [kit]\n")

    nodes, warnings = load_nodes(tmp_path)

    assert nodes["cli"].widens == {"kit": ""}
    assert any("widens" in w and "cli" in w for w in warnings)


def test_a_widens_scalar_is_empty_and_warns(tmp_path: Path) -> None:
    _manifest(tmp_path / "cli", "name: cli\nwidens: everything\n")

    nodes, warnings = load_nodes(tmp_path)

    assert nodes["cli"].widens == {}
    assert any("widens" in w and "cli" in w for w in warnings)


def test_load_nodes_writes_no_manifest(tmp_path: Path) -> None:
    _manifest(tmp_path / "core", "name: core\n")
    (tmp_path / "bare").mkdir()
    (tmp_path / "bare" / "mod.py").write_text("x = 1\n", encoding="utf-8")

    load_nodes(tmp_path)

    assert sorted(p.parent.name for p in tmp_path.rglob("context.yaml")) == ["core"]


def test_a_widens_key_without_a_value_has_an_empty_reason(tmp_path: Path) -> None:
    _manifest(tmp_path / "cli", "name: cli\nconsumes: [kit]\nwidens:\n  kit:\n")

    nodes, warnings = load_nodes(tmp_path)

    assert nodes["cli"].widens == {"kit": ""}
    assert warnings == []
