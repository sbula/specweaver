# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The AST code lives in `workspace/ast/`, and every boundary a `context.yaml` names exists.

Proves: TECH-003 FR-1
Proves: TECH-003 FR-2
Proves: TECH-003 FR-3

A `forbids` entry naming a moved package forbids nothing, and a `consumes` entry naming one
describes a dependency that is not there. 65 of 113 entries had gone stale this way over several
package moves before this test existed.

| Bucket | Case |
|---|---|
| Happy | every entry resolves to a package, a module or a glob that matches one |
| Boundary | a glob (`specweaver/sandbox/*`) counts when it matches at least one folder |
| Degradation | not applicable — the files are SpecWeaver's own |
| Hostile | not applicable — no input crosses a trust boundary |
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

_SRC = Path(__file__).resolve().parents[2] / "src"


def _entries() -> list[tuple[str, str, str]]:
    yaml = YAML(typ="safe")
    found = []
    for manifest in sorted(_SRC.rglob("context.yaml")):
        data = yaml.load(manifest.read_text(encoding="utf-8")) or {}
        for key in ("consumes", "forbids"):
            for entry in data.get(key) or []:
                name = str(entry).split("#")[0].strip()
                if name.startswith("specweaver"):
                    found.append((str(manifest.relative_to(_SRC)), key, name))
    return found


def _exists(name: str) -> bool:
    path = name.replace(".", "/").rstrip("/")
    if "*" in path:
        return any(_SRC.glob(path))
    return (_SRC / path).exists() or (_SRC / f"{path}.py").exists()


def test_every_boundary_names_a_real_path() -> None:
    stale = [entry for entry in _entries() if not _exists(entry[2])]

    assert stale == [], "\n".join(f"{f}: {key}: {name}" for f, key, name in stale)


def test_the_check_sees_the_manifests() -> None:
    assert len(_entries()) > 50


def test_the_parsers_and_adapters_live_under_workspace_ast() -> None:
    import importlib

    for name in ("parsers.factory", "adapters.graph_adapter"):
        importlib.import_module(f"specweaver.workspace.ast.{name}")
    assert not (_SRC / "specweaver" / "workspace" / "parsers").exists()
    assert not (_SRC / "specweaver" / "workspace" / "adapters").exists()
