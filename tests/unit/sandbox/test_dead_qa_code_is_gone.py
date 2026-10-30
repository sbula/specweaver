# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The dead QA code and the old copies stay deleted: one copy each, beside the runners.

Proves: TECH-087 FR-11
Proves: TECH-087 FR-14

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
        (
            "specweaver.sandbox.language.core.java",
            "specweaver.sandbox.language.core.java.stack_trace_filter",
        ),
        (
            "specweaver.sandbox.language.core.kotlin",
            "specweaver.sandbox.language.core.kotlin.stack_trace_filter",
        ),
        ("specweaver.sandbox.language.core", "specweaver.sandbox.language.core.maven_output"),
        ("specweaver.sandbox.language.core", "specweaver.sandbox.language.core.evaluator"),
        ("specweaver.workspace.ast.parsers", "specweaver.workspace.ast.parsers._sarif_complexity"),
        ("specweaver.workspace.ast.parsers.java", "specweaver.workspace.ast.parsers.java.parsers"),
        (
            "specweaver.workspace.ast.parsers.kotlin",
            "specweaver.workspace.ast.parsers.kotlin.parsers",
        ),
        (
            "specweaver.workspace.ast.parsers.typescript",
            "specweaver.workspace.ast.parsers.typescript.parsers",
        ),
    ],
)
def test_a_dead_module_is_gone(package: str, module: str) -> None:
    importlib.import_module(package)

    assert importlib.util.find_spec(module) is None
