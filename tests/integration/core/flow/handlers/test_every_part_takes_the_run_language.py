# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every part of a run takes the run's one language, even where the root's build files say another.

Proves: TECH-079 FR-7, TECH-079 FR-14

A root with `pyproject.toml`, `package.json` and `tsconfig.json`, pinned to Python: before
TECH-079 the QA runner and the scenario converter detected TypeScript from `package.json`. Real
handlers and factories; nothing is run.

| Bucket | Case |
|---|---|
| Happy | lint, unit tests, scenario tests, the scenario file and the stack trace filter are Python's; the same root pinned to TypeScript gets TypeScript's |
| Boundary | the scenario run (always in a container) takes the run's language too |
| Degradation | not applicable — the parts are chosen, not run |
| Hostile | an undecided run makes every part refuse, naming the setting, instead of picking one |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.commons.project_profile import ProjectProfile, ProjectUndecidedError
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.handlers.qa_targets import default_test_target
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.core.flow.run_state.run_context import IsolationPolicy, RunContext
from specweaver.sandbox.language.core.python.runner import PythonQARunner
from specweaver.sandbox.language.core.python.stack_trace_filter import PythonStackTraceFilter
from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner
from specweaver.sandbox.language.core.typescript.stack_trace_filter import (
    TypeScriptStackTraceFilter,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _context(root: Path, **isolation: object) -> RunContext:
    for name, text in {
        "pyproject.toml": "[project]\nname = 'x'\n",
        "package.json": "{}",
        "tsconfig.json": "{}",
    }.items():
        (root / name).write_text(text, encoding="utf-8")
    return RunContext(
        project_path=root,
        spec_path=root / "specs" / "greet_spec.md",
        isolation=IsolationPolicy(**isolation),
    )


def _runners(context: RunContext) -> list[type]:
    with patch("specweaver.sandbox.language.core.runner_factory._build_container_executor"):
        atoms = [
            LintFixHandler()._get_atom(context),
            ValidateTestsHandler()._get_atom(context, "unit"),
            ValidateTestsHandler()._get_atom(context, "scenario"),
        ]
    return [type(atom._runner) for atom in atoms]


def _filter(context: RunContext) -> type:
    from specweaver.core.flow.handlers.arbiter import trace_filter

    return type(trace_filter(context))


def test_a_run_pinned_to_python_is_python_everywhere(tmp_path: Path) -> None:
    context = _context(tmp_path, profile=ProjectProfile("python", "uv"))

    assert _runners(context) == [PythonQARunner] * 3
    assert default_test_target(context, "scenario").endswith("test_greet_scenarios.py")
    assert _filter(context) is PythonStackTraceFilter


def test_the_same_root_pinned_to_typescript_is_typescript_everywhere(tmp_path: Path) -> None:
    context = _context(tmp_path, profile=ProjectProfile("typescript", "npm"))

    assert _runners(context) == [TypeScriptRunner] * 3
    assert default_test_target(context, "scenario").endswith(".ts")
    assert _filter(context) is TypeScriptStackTraceFilter


def test_an_undecided_run_makes_every_part_refuse(tmp_path: Path) -> None:
    context = _context(tmp_path, undecided="set [implement] language in specweaver.toml")

    for part in (
        lambda: LintFixHandler()._get_atom(context),
        lambda: ValidateTestsHandler()._get_atom(context, "scenario"),
        lambda: default_test_target(context, "scenario"),
        lambda: _filter(context),
    ):
        with pytest.raises(ProjectUndecidedError, match=r"set \[implement\] language"):
            part()
