# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw init` writes a project's module boundaries, with no model and no agent tool.

Proves: C-FLOW-06 FR-4

| Bucket | Case |
|---|---|
| Happy | root, `src` and `tests` each get a `context.yaml` that the topology graph reads |
| Boundary | `sw init` keeps a boundary the project already has |
| Degradation | not applicable: nothing is fetched or generated |
| Hostile | no model is called |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typer.testing import CliRunner

from specweaver.assurance.graph.topology import TopologyGraph
from specweaver.graph.topology.engine import TopologyEngine
from specweaver.interfaces.cli.main import app
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


class _NoModel:
    def available(self) -> bool:
        return True

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("sw init must not call a model")

    generate_with_tools = generate


def test_init_writes_boundaries_the_graph_reads(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-4
    with doubled_llm(_NoModel()):
        result = runner.invoke(app, ["init", "demo", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output

    for folder in (tmp_path, tmp_path / "src", tmp_path / "tests"):
        assert (folder / "context.yaml").is_file(), folder
    graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
    assert len(graph.nodes) == 3
    assert "specweaver/sandbox/*" in graph.nodes[_name_of(graph, tmp_path / "src")].forbids


def test_init_keeps_a_boundary_the_project_already_has(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-4
    own = "name: mine\nlevel: service\n"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "context.yaml").write_text(own, encoding="utf-8")

    assert runner.invoke(app, ["init", "demo", "--path", str(tmp_path)]).exit_code == 0

    assert (tmp_path / "src" / "context.yaml").read_text(encoding="utf-8") == own


def _name_of(graph: TopologyGraph, folder: Path) -> str:
    return next(n for n, node in graph.nodes.items() if node.yaml_path.parent == folder)
