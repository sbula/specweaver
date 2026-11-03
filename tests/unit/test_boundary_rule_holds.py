# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SpecWeaver's own manifests obey the boundary rule it ships.

Proves: TECH-082 FR-21

The rule `[agreed 2026-11-03]`: going down the folder tree a module gets stricter, and widens only
where its `context.yaml` declares it in `widens`, with a reason. The resolver here is the one the
product uses, so our tree cannot pass a weaker check than a user's project.

| Bucket | Case |
|---|---|
| Happy | no manifest breaks the rule |
| Boundary | every `tach.toml` edge is one the rule allows its module |
| Degradation | every `context.yaml` is loaded: a parse error or a name clash would drop one |
| Hostile | the check finds the manifests at all: a wrong root would pass on nothing |
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from specweaver.assurance.graph.boundary_rule import allows, breaches
from specweaver.assurance.graph.topology import load_nodes

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"


def _report(found: list) -> str:
    return "\n".join(f"{b.folder}: {b.kind}: {b.entry} (parent {b.parent})" for b in found)


def _edge_allowed(nodes: dict, module: str, target: str) -> bool:
    """A tach module is coarser than a manifest entry: `sandbox` is one tach module, while a
    manifest may consume and widen only `sandbox/execution`. The edge holds when the target itself,
    or a part of it the manifest consumes, is allowed."""
    folder, wanted = module.replace(".", "/"), target.replace(".", "/")
    if allows(nodes, _SRC, folder, wanted):
        return True
    owners = [node for node in nodes.values() if node.yaml_path.parent == _SRC / folder]
    if not owners:  # a one-file module has no manifest of its own; its parent's rule decided
        return False
    parts = [str(c) for c in owners[0].consumes if str(c).startswith(wanted + "/")]
    return any(allows(nodes, _SRC, folder, part) for part in parts)


def test_no_manifest_breaks_the_rule() -> None:
    nodes, _ = load_nodes(_SRC)

    found = breaches(nodes, _SRC)

    assert found == [], _report(found)


def test_every_tach_edge_is_allowed_by_the_rule() -> None:
    nodes, _ = load_nodes(_SRC)
    with (_ROOT / "tach.toml").open("rb") as f:
        modules = tomllib.load(f)["modules"]

    refused = [
        f"{m['path']} -> {target}"
        for m in modules
        for target in m.get("depends_on", [])
        if isinstance(target, str) and not _edge_allowed(nodes, m["path"], target)
    ]

    assert refused == []


def test_every_manifest_is_loaded() -> None:
    files = sorted(_SRC.rglob("context.yaml"))

    nodes, warnings = load_nodes(_SRC)

    assert warnings == []
    assert len(nodes) == len(files)


def test_the_check_sees_the_manifests() -> None:
    nodes, _ = load_nodes(_SRC)

    assert len(nodes) > 50
    assert load_nodes(_SRC / "no_such_folder")[0] == {}
