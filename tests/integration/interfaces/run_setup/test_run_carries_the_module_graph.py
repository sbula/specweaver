# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run setup hands a run the module graph's three meanings, each in its own field.

Proves: TECH-088 FR-1, TECH-088 FR-12, TECH-088 FR-13, TECH-088 FR-14
Proves: TECH-088 FR-6

The slot used to be one `Any` field that held a list, while three readers wanted one context, a
node and a graph. Every case here builds its run with the real run setup on real `context.yaml`
files, so the shapes are the ones a user's run gets.

| Bucket | Case |
|---|---|
| Happy | `billing` gets `payments` as its related context, itself as the target boundary with its server, and a graph whose impact of `payments` is `billing` |
| Boundary | a module with no neighbours still gets its target boundary; a project with no `context.yaml` gets `None` in all three |
| Degradation | `context.yaml` files exist but none names the spec's module: one WARNING names it, and the three fields are `None` |
| Hostile | no warning when there is no `context.yaml` at all, or when the name matches |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from specweaver.interfaces.run_setup.builder import build_run_sync
from tests.fixtures.module_graph_project import RESOURCE, module_graph_project, run_request

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_LOGGER = "specweaver.interfaces.run_setup.builder"


def _warnings_naming(caplog: pytest.LogCaptureFixture, stem: str) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == _LOGGER
        and record.levelno == logging.WARNING
        and f"'{stem}'" in record.getMessage()
    ]


def test_a_module_with_a_neighbour_gets_all_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch)

    graph = build_run_sync(run_request(db, root, "billing")).graph

    assert [c.name for c in graph.related_contexts or []] == ["payments"]
    assert graph.target_boundary is not None
    assert graph.target_boundary.name == "billing"
    assert "invoices" in graph.target_boundary.mcp_servers
    assert graph.target_boundary.consumes_resources == (RESOURCE,)
    assert graph.module_graph is not None
    assert graph.module_graph.impact_of("payments") == {"billing"}


def test_a_module_with_no_neighbours_still_gets_its_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch, servers_on="solo")

    graph = build_run_sync(run_request(db, root, "solo")).graph

    assert graph.related_contexts is None
    assert graph.target_boundary is not None
    assert graph.target_boundary.consumes_resources == (RESOURCE,)


def test_a_project_without_manifests_gets_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch, manifests=False)

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        graph = build_run_sync(run_request(db, root, "billing")).graph

    assert (graph.related_contexts, graph.target_boundary, graph.module_graph) == (None, None, None)
    assert _warnings_naming(caplog, "billing") == []


def test_a_module_no_manifest_names_is_warned_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch)

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        graph = build_run_sync(run_request(db, root, "orphan")).graph

    assert _warnings_naming(caplog, "orphan") == [
        "No context.yaml names module 'orphan': topology context and MCP pre-fetch are off "
        "for this run."
    ]
    assert graph.related_contexts is None
    assert graph.target_boundary is None


def test_a_matching_module_is_not_warned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db, root = module_graph_project(tmp_path, monkeypatch)

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        build_run_sync(run_request(db, root, "billing"))

    assert _warnings_naming(caplog, "billing") == []


def test_the_runs_module_graph_cannot_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-13: every step shares the run's graph, so the run setup hands over a frozen one."""
    from specweaver.graph.topology.engine import FrozenGraphError

    db, root = module_graph_project(tmp_path, monkeypatch)
    graph = build_run_sync(run_request(db, root, "billing")).graph.module_graph
    assert graph is not None

    with pytest.raises(FrozenGraphError):
        graph._engine.add_edge("payments", "billing")  # type: ignore[attr-defined]
    assert graph.impact_of("billing") == set()


def test_the_runs_boundary_and_contexts_cannot_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-14: the boundary and the contexts are shared by every step too, so none takes a write."""
    db, root = module_graph_project(tmp_path, monkeypatch, servers_on="payments")
    graph = build_run_sync(run_request(db, root, "billing")).graph
    boundary = graph.target_boundary
    neighbour = (graph.related_contexts or [])[0]
    assert boundary is not None

    with pytest.raises(AttributeError):
        boundary.consumes.append("x")  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        neighbour.mcp_servers["invoices"]["args"].append("--evil")
    with pytest.raises(TypeError):
        neighbour.mcp_servers["invoices"]["env"] = {}  # type: ignore[index]
    with pytest.raises(AttributeError):
        neighbour.constraints.append("x")  # type: ignore[attr-defined]
