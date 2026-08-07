# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Guards the interface layer against regrowing the private helpers it was cleaned of.

Five helpers held domain logic and infrastructure wiring inside the CLI layer, and a dozen
other modules — including the REST API — imported them across interface boundaries. They were
deleted in favour of the public APIs they wrapped. Nothing stopped them coming back, so these
tests assert the absence directly rather than trusting that nobody re-adds one.

Proves: TECH-006 FR-1, FR-2, FR-3, FR-4, FR-5.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[4] / "src" / "specweaver"

#: helper name -> the module it used to live in, and the public API that replaced it.
DELETED_HELPERS = {
    "_load_constitution_content": ("workspace/project/interfaces/cli.py", "find_constitution()"),
    "_load_standards_content": (
        "assurance/standards/interfaces/cli.py",
        "load_standards_content()",
    ),
    "_require_llm_adapter": ("infrastructure/llm/interfaces/cli.py", "create_llm_adapter()"),
    "_load_topology": ("graph/interfaces/cli.py", "the assurance.graph facade"),
    "_select_topology_contexts": ("graph/interfaces/cli.py", "the assurance.graph facade"),
}


def _defined_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}


@pytest.mark.parametrize(("helper", "spec"), sorted(DELETED_HELPERS.items()))
def test_helper_is_not_redefined(helper: str, spec: tuple[str, str]) -> None:
    """The helper stays gone from the module it was removed from."""
    module, replacement = spec
    path = SRC / module
    assert path.exists(), f"{module} moved; update this guard"

    assert helper not in _defined_names(path), (
        f"{helper} is back in {module}. Call {replacement} directly instead."
    )


def test_no_module_imports_a_deleted_helper() -> None:
    """Nothing anywhere imports one of them, which is what made them spread in the first place."""
    offenders = [
        f"{path.relative_to(SRC)}: {helper}"
        for path in SRC.rglob("*.py")
        for helper in DELETED_HELPERS
        if f"import {helper}" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_the_api_layer_does_not_import_the_cli_layer() -> None:
    """The REST API reached into CLI modules for those helpers. It must not do so again."""
    api = SRC / "interfaces" / "api"
    offenders = []
    for path in api.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and "interfaces.cli" in node.module:
                offenders.append(f"{path.relative_to(SRC)} -> {node.module}")

    assert offenders == []


def test_run_repo_op_is_the_one_typed_replacement() -> None:
    """The string-dispatched `_run_workspace_op` had two copies; a single typed helper replaced
    them. Both copies staying gone is the point."""
    from specweaver.interfaces.cli import _core

    assert callable(_core.run_repo_op)
    assert "_run_workspace_op" not in _defined_names(SRC / "workspace/project/interfaces/cli.py")
    assert "_run_workspace_op" not in _defined_names(SRC / "core/config/interfaces/cli.py")
