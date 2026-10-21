# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real-toolchain journeys stay out of the default run, and skip only on the machine's own facts.

Proves: D-INTL-08 NFR-3

They download packages and start Maven, Gradle, npm and cargo: minutes, and a network. The default
suite uses doubled runners `[agreed 2026-10-20]`; these run in the `toolchain` tier, nightly.

| Bucket | Case |
|---|---|
| Happy | the marker is registered, and a bare `pytest` deselects it |
| Boundary | every test in the journey file carries the marker |
| Degradation | not applicable — this reads configuration, nothing runs |
| Hostile | a skip in the journey names a tool or a registry, never repo state |
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
JOURNEY = (
    REPO_ROOT
    / "tests"
    / "e2e"
    / "capabilities"
    / "workflows"
    / "test_implement_with_real_toolchains_e2e.py"
)


def _pytest_options() -> dict:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["tool"]["pytest"]["ini_options"]


def test_the_marker_is_registered() -> None:
    assert any(marker.startswith("toolchain:") for marker in _pytest_options()["markers"])


def test_a_bare_pytest_run_deselects_the_toolchain_tier() -> None:
    expression = re.search(r"-m\s*'([^']*)'", _pytest_options()["addopts"])

    assert expression is not None
    assert re.search(r"\bnot\s+toolchain\b", expression.group(1))
    assert re.search(r"\bnot\s+live\b", expression.group(1))


def test_the_journey_carries_the_marker() -> None:
    tree = ast.parse(JOURNEY.read_text(encoding="utf-8"))
    marks = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets)
    ]

    assert marks, "the journey file sets no pytestmark"
    assert "toolchain" in ast.unparse(marks[0].value)


def test_a_skip_names_only_a_tool_or_a_registry() -> None:
    source = JOURNEY.read_text(encoding="utf-8")
    reasons = re.findall(r'pytest\.skip\(f?"([^"]+)"', source)
    reasons += re.findall(r'reason=f?"([^"]+)"', source)

    assert reasons
    for reason in reasons:
        assert re.match(r"toolchain not installed: |package registry unreachable: ", reason), reason
