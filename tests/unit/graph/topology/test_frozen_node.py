# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A loaded `TopologyNode` cannot change at any depth, its `OperationalMetadata` and contexts neither.

Proves: TECH-088 FR-14

Every step of a run shares the node, so a write by one step would reach every later one.

| Bucket | Case |
|---|---|
| Happy | a node loaded from a `context.yaml` with every field refuses each write, down to `mcp_servers["s"]["env"]` |
| Boundary | a node built in a test from plain lists is just as frozen; empty fields are empty tuples and maps |
| Degradation | a `context.yaml` whose server config holds a value that cannot be frozen is skipped with a warning; the other nodes load |
| Hostile | the caller's list, changed after building, does not reach the node; a `TopologyContext` built from a node is frozen too |
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest

from specweaver.commons.topology_context import TopologyContext
from specweaver.graph.topology.topology import OperationalMetadata, TopologyNode, load_nodes

if TYPE_CHECKING:
    from pathlib import Path

_MANIFEST = """name: billing
level: module
purpose: Bills customers.
archetype: adapter
consumes:
  - payments
exposes:
  - invoice
forbids:
  - specweaver/cli
constraints:
  - no network
consumes_resources:
  - mcp://s/table
widens:
  specweaver/x: needed for y
operational:
  max_latency_ms: 50
mcp_servers:
  s:
    command: [python]
    args: [server.py]
    env:
      K: v
"""


@pytest.fixture
def node(tmp_path: Path) -> TopologyNode:
    (tmp_path / "billing").mkdir()
    (tmp_path / "billing" / "context.yaml").write_text(_MANIFEST, encoding="utf-8")
    nodes, _ = load_nodes(tmp_path)
    return nodes["billing"]


def test_no_field_can_be_assigned(node: TopologyNode) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.consumes = ["other"]  # type: ignore[misc]
    assert node.operational is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.operational.max_latency_ms = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    "field", ["consumes", "exposes", "forbids", "constraints", "consumes_resources"]
)
def test_no_list_can_grow(node: TopologyNode, field: str) -> None:
    value = getattr(node, field)

    assert isinstance(value, tuple)
    with pytest.raises(AttributeError):
        value.append("x")  # type: ignore[attr-defined]


def test_no_map_can_change_at_any_depth(node: TopologyNode) -> None:
    server = node.mcp_servers["s"]

    with pytest.raises(TypeError):
        node.widens["specweaver/z"] = "why"  # type: ignore[index]
    with pytest.raises(TypeError):
        node.mcp_servers["t"] = {}  # type: ignore[index]
    with pytest.raises(AttributeError):
        server["args"].append("--evil")
    with pytest.raises(TypeError):
        server["env"]["K"] = "changed"


def test_the_loaded_values_are_the_declared_ones(node: TopologyNode) -> None:
    assert node.consumes == ("payments",)
    assert node.widens == {"specweaver/x": "needed for y"}
    assert node.mcp_servers == {
        "s": {"command": ("python",), "args": ("server.py",), "env": {"K": "v"}}
    }
    assert node.operational == OperationalMetadata(max_latency_ms=50)


def test_a_node_built_from_plain_lists_is_frozen_and_keeps_none_of_them() -> None:
    consumes = ["payments"]
    servers = {"s": {"args": ["a"]}}
    built = TopologyNode("n", "module", "p", "adapter", consumes=consumes, mcp_servers=servers)

    consumes.append("x")
    servers["s"]["args"].append("b")

    assert built.consumes == ("payments",)
    assert built.mcp_servers["s"]["args"] == ("a",)


def test_empty_fields_are_empty_and_frozen() -> None:
    built = TopologyNode("n", "module", "p", "adapter")

    assert built.consumes == ()
    with pytest.raises(TypeError):
        built.mcp_servers["s"] = {}  # type: ignore[index]


def test_a_context_built_from_a_node_is_frozen_too(node: TopologyNode) -> None:
    context = TopologyContext(
        "billing",
        "p",
        "adapter",
        "direct dependency",
        constraints=["c"],
        mcp_servers=dict(node.mcp_servers),
        consumes_resources=["r"],
    )

    assert context.constraints == ("c",)
    assert context.consumes_resources == ("r",)
    with pytest.raises(TypeError):
        context.mcp_servers["t"] = {}  # type: ignore[index]


def test_a_value_that_cannot_be_frozen_skips_that_node(tmp_path: Path) -> None:
    for name, extra in (("ok", ""), ("odd", "mcp_servers:\n  s:\n    command: !custom docker\n")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "context.yaml").write_text(
            f"name: {name}\npurpose: p\narchetype: adapter\n{extra}", encoding="utf-8"
        )

    nodes, warnings = load_nodes(tmp_path)

    assert list(nodes) == ["ok"]
    assert any("odd" in w and "cannot freeze" in w for w in warnings), warnings
