from pathlib import Path

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
    graph = TopologyGraph(nodes={"api": node})

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
    graph = TopologyGraph(nodes={"domain": node})

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
    graph = TopologyGraph(nodes={"new_module": node})

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
    graph = TopologyGraph(nodes={})

    with pytest.raises(ParseError):
        sync_tach_toml(graph, tmp_path)


def test_sync_tach_toml_empty_graph(tmp_path: Path) -> None:
    graph = TopologyGraph(nodes={})
    result = sync_tach_toml(graph, tmp_path)

    assert result.modules_synced == 0
    assert result.interfaces_synced == 0

    doc = tomlkit.parse((tmp_path / "tach.toml").read_text("utf-8"))
    assert "modules" not in doc
    assert "interfaces" not in doc
    assert doc["exact"] is True
