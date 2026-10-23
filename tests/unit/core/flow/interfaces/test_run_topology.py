# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run gets the topology slice around its spec's module, when the project has a topology.

| Bucket | Case |
|---|---|
| Happy | a topology gives the slice selected for the spec's module and the selector |
| Boundary | no topology leaves the context's graph unchanged |
| Degradation | not applicable — loading a broken topology is `load_topology`'s, tested there |
| Hostile | not applicable — the spec name only selects a module; nothing is read from it |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.interfaces import run_topology

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_a_topology_gives_the_selected_slice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[object, str, str]] = []
    monkeypatch.setattr(run_topology, "load_topology", lambda _root: "GRAPH")

    def select(graph: object, module: str, *, selector_name: str) -> list[str]:
        seen.append((graph, module, selector_name))
        return ["slice"]

    monkeypatch.setattr(run_topology, "select_topology_contexts", select)
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "orders_spec.md")

    run_topology.attach_topology(context, tmp_path, tmp_path / "orders_spec.md", "nhop")

    assert seen == [("GRAPH", "orders", "nhop")]
    assert context.graph.topology == ["slice"]


def test_no_topology_leaves_the_graph_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_topology, "load_topology", lambda _root: None)
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "orders_spec.md")
    before = context.graph

    run_topology.attach_topology(context, tmp_path, tmp_path / "orders_spec.md", "nhop")

    assert context.graph == before
