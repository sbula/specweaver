# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's service name is the name in the `context.yaml` at its root.

Proves: TECH-004 FR-6

Real projects in a temporary folder, read by the real topology loader. The earlier tests used mocks
with a `path` field that a topology node does not have, so they passed while the function always
answered `default`.

| Bucket | Case |
|---|---|
| Happy | a root `context.yaml` named `billing` gives `billing` |
| Boundary | the project path given with `..` in it; the root named among several modules |
| Degradation | no topology; a topology with no root module |
| Hostile | only a sub-module has a `context.yaml`: its name is not taken for the project |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.graph.loader import load_topology, resolve_service_name

if TYPE_CHECKING:
    from pathlib import Path


def _write_context(directory: Path, *, name: str, consumes: list[str] | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f"name: {name}", "level: module", "purpose: Test module.", "archetype: pure-logic"]
    if consumes:
        lines.append("consumes: [" + ", ".join(consumes) + "]")
    (directory / "context.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_the_root_context_names_the_service(tmp_path: Path) -> None:
    _write_context(tmp_path, name="billing")
    assert resolve_service_name(load_topology(tmp_path), tmp_path) == "billing"


def test_the_root_is_found_among_its_modules(tmp_path: Path) -> None:
    _write_context(tmp_path / "a", name="a")
    _write_context(tmp_path, name="billing", consumes=["a"])
    _write_context(tmp_path / "z", name="z")
    assert resolve_service_name(load_topology(tmp_path), tmp_path) == "billing"


def test_a_path_with_dots_is_resolved(tmp_path: Path) -> None:
    _write_context(tmp_path, name="billing")
    (tmp_path / "sub").mkdir()
    assert resolve_service_name(load_topology(tmp_path), tmp_path / "sub" / "..") == "billing"


def test_no_topology_is_default(tmp_path: Path) -> None:
    assert resolve_service_name(None, tmp_path) == "default"


def test_a_sub_module_does_not_name_the_project(tmp_path: Path) -> None:
    _write_context(tmp_path / "src" / "a", name="a")
    topology = load_topology(tmp_path)
    assert topology is not None and topology.nodes
    assert resolve_service_name(topology, tmp_path) == "default"
