# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Writing a project's topology out as its `tach.toml`.

Proves: C-EXEC-01 FR-5

Cited under `specweaver-dev` §3.2c, from `INT-US-01-SF02-MIG`. FR-5 is new: SF-08 shipped this adapter
and no requirement described it.

**The purge needed the right mutant.** `sync_tach_toml` deletes `[[modules]]` before rebuilding it,
because the graph is the source of truth. Disabling that `del` with a populated graph passed the whole
suite — an **equivalent mutant**, since `doc["modules"] = ...` replaces the key anyway. The `del` is
only observable when there is nothing to assign: the rebuild is guarded by `modules_count > 0`, so an
*emptied* topology is the case where a missing purge leaves every old boundary in force and tach goes
on checking a shape the project no longer declares.

`test_sync_tach_toml_with_an_empty_graph_clears_stale_bounds` is that case, and it kills the mutant.
Recorded because the first attempt looked like a coverage gap and was not one — it was a mutant that
changed no behaviour.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import tomlkit
from tomlkit.exceptions import ParseError

from specweaver.assurance.graph.topology import TopologyGraph, TopologyNode
from specweaver.workspace.project.tach_sync import sync_tach_toml


def test_sync_tach_toml_empty_creates_new(tmp_path: Path) -> None:
    # Setup simple arbitrary graph
    node = TopologyNode(
        name="api",
        level="system",
        purpose="Test API",
        archetype="adapter",
        consumes=["cli", "config"],
        exposes=[],
    )
    graph = TopologyGraph(nodes={"api": node}, engine=MagicMock())

    target_path = tmp_path
    tach_file = target_path / "tach.toml"
    assert not tach_file.exists()

    result = sync_tach_toml(graph, target_path)

    # Validate Result
    assert result.modules_synced == 1
    assert result.interfaces_synced == 0
    assert result.path == tach_file

    # Validate output written
    assert tach_file.exists()
    doc = tomlkit.parse(tach_file.read_text("utf-8"))

    # Assert root properties
    assert doc["exclude"] == []
    assert doc["source_roots"] == ["."]
    assert doc["exact"] is True

    # Assert modules
    modules = doc.get("modules", [])
    assert len(modules) == 1
    assert modules[0]["path"] == "api"
    assert modules[0]["depends_on"] == ["cli", "config"]

    # Assert no interfaces written for empty exposes
    assert "interfaces" not in doc


def test_sync_tach_toml_interface_mapping(tmp_path: Path) -> None:
    # Setup simple arbitrary graph
    node = TopologyNode(
        name="domain",
        level="module",
        purpose="Domain logic",
        archetype="pure-logic",
        consumes=[],
        exposes=["runner", "core"],
    )
    graph = TopologyGraph(nodes={"domain": node}, engine=MagicMock())

    result = sync_tach_toml(graph, tmp_path)

    # Validate Result
    assert result.modules_synced == 1
    assert result.interfaces_synced == 1

    doc = tomlkit.parse((tmp_path / "tach.toml").read_text("utf-8"))

    interfaces = doc.get("interfaces", [])
    assert len(interfaces) == 1
    assert interfaces[0]["from"] == ["domain"]
    assert interfaces[0]["expose"] == ["core", "runner"]


def test_sync_tach_toml_deep_merge(tmp_path: Path) -> None:
    # Pre-populate an existing tach.toml with custom properties
    tach_file = tmp_path / "tach.toml"
    tach_file.write_text(
        'exclude = ["venv", "dist"]\n'
        "custom_property = 42\n"
        "\n"
        "[[modules]]\n"
        'path = "old_module"\n'
        'depends_on = ["old_dep"]\n',
        encoding="utf-8",
    )

    node = TopologyNode(
        name="new_module",
        level="module",
        purpose="New logic",
        archetype="adapter",
        consumes=["new_dep"],
        exposes=[],
    )
    graph = TopologyGraph(nodes={"new_module": node}, engine=MagicMock())

    result = sync_tach_toml(graph, tmp_path)

    assert result.modules_synced == 1
    assert result.interfaces_synced == 0

    doc = tomlkit.parse(tach_file.read_text("utf-8"))

    # Assert root properties are preserved completely
    assert doc["exclude"] == ["venv", "dist"]
    assert doc["custom_property"] == 42
    assert "source_roots" in doc
    assert doc["exact"] is True

    # Assert old module is gone, replaced entirely by new module
    modules = doc.get("modules", [])
    assert len(modules) == 1
    assert modules[0]["path"] == "new_module"
    assert modules[0]["depends_on"] == ["new_dep"]


def test_sync_tach_toml_malformed(tmp_path: Path) -> None:
    tach_file = tmp_path / "tach.toml"
    tach_file.write_text("[[modules]\nbad_syntax...", encoding="utf-8")
    graph = TopologyGraph(nodes={}, engine=MagicMock())

    with pytest.raises(ParseError):
        sync_tach_toml(graph, tmp_path)


def test_sync_tach_toml_empty_graph(tmp_path: Path) -> None:
    graph = TopologyGraph(nodes={}, engine=MagicMock())
    result = sync_tach_toml(graph, tmp_path)

    assert result.modules_synced == 0
    assert result.interfaces_synced == 0

    doc = tomlkit.parse((tmp_path / "tach.toml").read_text("utf-8"))
    assert "modules" not in doc
    assert "interfaces" not in doc
    assert doc["exact"] is True


def test_sync_tach_toml_purges_modules_the_graph_no_longer_has(tmp_path: Path) -> None:
    """A module deleted from the topology loses its `tach.toml` boundary rules.

    `C-EXEC-01` FR-5. The graph is the source of truth, so a sync REBUILDS `[[modules]]` rather than
    merging into it — otherwise a module removed from `context.yaml` keeps being enforced, and tach
    checks a project shape that no longer exists.

    Nothing tested the purge: disabling `del doc["modules"]` passed the whole suite. The existing
    tests all sync into a file whose modules are a subset of the graph's, where rebuild and merge are
    indistinguishable.
    """
    tach_file = tmp_path / "tach.toml"
    tach_file.write_text(
        tomlkit.dumps(
            tomlkit.parse(
                'source_roots = ["."]\n'
                "\n"
                "[[modules]]\n"
                'path = "legacy"\n'
                'depends_on = ["config"]\n'
                "\n"
                "[[modules]]\n"
                'path = "api"\n'
                'depends_on = ["legacy"]\n'
            )
        ),
        encoding="utf-8",
    )

    node = TopologyNode(
        name="api",
        level="system",
        purpose="Test API",
        archetype="adapter",
        consumes=["config"],
        exposes=[],
    )
    graph = TopologyGraph(nodes={"api": node}, engine=MagicMock())

    result = sync_tach_toml(graph, tmp_path)

    assert result.modules_synced == 1
    doc = tomlkit.parse(tach_file.read_text("utf-8"))
    paths = [m["path"] for m in doc.get("modules", [])]
    assert paths == ["api"], f"stale module bounds survived the sync: {paths}"
    assert doc["modules"][0]["depends_on"] == ["config"], (
        "the graph's edges must replace the file's, not merge with them"
    )


def test_sync_tach_toml_with_an_empty_graph_clears_stale_bounds(tmp_path: Path) -> None:
    """A project that declares no topology ends up enforcing none.

    `C-EXEC-01` FR-5, and this is the case the explicit purge exists for. When the graph has modules,
    `doc["modules"] = ...` replaces the key on its own and the `del` above it changes nothing — the
    first attempt at this test disabled the `del` and the suite stayed green for exactly that reason,
    an equivalent mutant rather than a gap.

    The purge is only observable when there is nothing to assign: `doc["modules"] = ...` is guarded by
    `modules_count > 0`, so without the `del` an emptied topology leaves every old boundary in force
    and tach goes on checking a shape the project no longer declares.
    """
    tach_file = tmp_path / "tach.toml"
    tach_file.write_text(
        'source_roots = ["."]\n\n[[modules]]\npath = "legacy"\ndepends_on = ["config"]\n',
        encoding="utf-8",
    )

    result = sync_tach_toml(TopologyGraph(nodes={}, engine=MagicMock()), tmp_path)

    assert result.modules_synced == 0
    doc = tomlkit.parse(tach_file.read_text("utf-8"))
    assert "modules" not in doc, f"stale bounds outlived an emptied topology: {doc}"
