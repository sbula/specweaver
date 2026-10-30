# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The dead QA code stays deleted: no run used it, so no test keeps it alive.

Proves: TECH-087 FR-11

Each case imports the parent first, so a wrong path fails instead of passing.

| Bucket | Case |
|---|---|
| Happy | each parent module imports, and the dead name is not in it |
| Boundary | a whole dead module: its package imports, the module is not found |
| Degradation | not applicable — a deletion has no failure mode at run time |
| Hostile | not applicable — nothing takes input |
"""

from __future__ import annotations

import importlib
import importlib.util

import pytest

_DEAD_NAMES = [
    ("specweaver.sandbox.language.core.java.runner", "_harvest_junit"),
    ("specweaver.sandbox.language.core.rust.runner", "_tally_junit"),
]


@pytest.mark.parametrize(("module", "name"), _DEAD_NAMES)
def test_a_dead_function_is_gone(module: str, name: str) -> None:
    assert not hasattr(importlib.import_module(module), name)


def test_the_dead_kotlin_reader_is_gone() -> None:
    from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

    assert not hasattr(KotlinRunner, "_parse_junit_results")


@pytest.mark.parametrize(
    ("package", "module"),
    [
        ("specweaver.workspace.ast.parsers.rust", "specweaver.workspace.ast.parsers.rust.parsers"),
        ("specweaver.sandbox", "specweaver.sandbox.rule_atom"),
    ],
)
def test_a_dead_module_is_gone(package: str, module: str) -> None:
    importlib.import_module(package)

    assert importlib.util.find_spec(module) is None
