# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each module's manifest declares every dependency `tach.toml` allows it, and forbids none of them.

Proves: TECH-081 FR-4, TECH-081 FR-7

`tach.toml` and the `context.yaml` files are both written by hand `[agreed 2026-10-27]`; this test is
what keeps them saying the same thing. A `deprecated` edge is owed in the ledger, not declared.

| Bucket | Case |
|---|---|
| Happy | every plain `depends_on` target is covered by a `consumes` entry |
| Boundary | a `consumes` entry covers a target it contains or a part of it; one-file modules have no manifest |
| Degradation | a module with no manifest of its own is named, not skipped |
| Hostile | a `forbids` entry naming an allowed target fails |
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from ruamel.yaml import YAML

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_NEW_MANIFESTS = (
    "sandbox",
    "workflows/scenarios",
    "workflows/evaluators",
    "workspace/memory",
    "core/flow/engine",
    "core/flow/handlers",
    "graph/lineage",
)


def _dotted(entry: str) -> str:
    return str(entry).split("#")[0].strip().replace("/", ".").removesuffix(".*").removesuffix("*")


def _covers(declared: str, target: str) -> bool:
    return (
        declared == target or target.startswith(declared + ".") or declared.startswith(target + ".")
    )


def _modules() -> list[tuple[str, list[str]]]:
    with (_ROOT / "tach.toml").open("rb") as f:
        modules = tomllib.load(f)["modules"]
    return [
        (m["path"], [d for d in m.get("depends_on", []) if isinstance(d, str)]) for m in modules
    ]


def _manifest(module: str) -> dict | None:
    folder = _SRC / module.replace(".", "/")
    if not folder.is_dir():
        return None
    path = folder / "context.yaml"
    return (YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def test_every_package_module_has_its_own_manifest() -> None:
    without = [
        m for m, _ in _modules() if _manifest(m) is not None and not _manifest(m).get("name")
    ]

    assert without == []


def test_every_allowed_dependency_is_declared() -> None:
    undeclared = []
    for module, targets in _modules():
        manifest = _manifest(module)
        if not manifest:
            continue
        consumes = [_dotted(c) for c in manifest.get("consumes") or []]
        undeclared += [
            f"{module} -> {t}" for t in targets if not any(_covers(c, t) for c in consumes)
        ]

    assert undeclared == []


def test_no_manifest_forbids_what_tach_allows() -> None:
    clashes = []
    for module, targets in _modules():
        forbids = [_dotted(f) for f in (_manifest(module) or {}).get("forbids") or []]
        clashes += [
            f"{module} forbids {t}"
            for t in targets
            if any(t == f or t.startswith(f + ".") for f in forbids)
        ]

    assert clashes == []


def test_the_missing_manifests_exist() -> None:
    absent = [d for d in _NEW_MANIFESTS if not (_SRC / "specweaver" / d / "context.yaml").exists()]

    assert absent == []


def test_a_part_or_a_whole_covers_a_target() -> None:
    assert _covers("specweaver.sandbox", "specweaver.sandbox")
    assert _covers("specweaver.workspace", "specweaver.workspace.ast.parsers")
    assert _covers("specweaver.sandbox.git.core", "specweaver.sandbox")
    assert not _covers("specweaver.work", "specweaver.workspace")
    assert _dotted("specweaver/sandbox/*  # comment") == "specweaver.sandbox"
