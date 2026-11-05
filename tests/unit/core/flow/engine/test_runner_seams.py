# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The runner's helpers reach it through one typed protocol, never through its private fields.

Proves: TECH-082 FR-7

| Bucket | Case |
|---|---|
| Happy | no engine module touches another object's `_` field; every `runner` parameter is a `RunnerPort` |
| Boundary | a fresh runner is a `RunnerPort` with both session flags off; `self._x` and dunders pass |
| Degradation | a file that does not parse is named, not skipped |
| Hostile | `getattr(runner, "_x")`, `setattr`/`hasattr` with a `_` literal and `x._y` are each found |
"""

from __future__ import annotations

import ast
from pathlib import Path

from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.runner_port import RunnerPort
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.run_state.run_context import RunContext

_ENGINE = Path(__file__).resolve().parents[5] / "src" / "specweaver" / "core" / "flow" / "engine"
_BY_NAME = ("getattr", "setattr", "hasattr", "delattr")


def _private(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # expected: named by the callers, so an unreadable file cannot pass
        return None


def _private_reads(path: Path) -> list[str]:
    """Each touch of another object's `_`-prefixed attribute in `path`, as `file:line`."""
    tree = _parse(path)
    if tree is None:
        return [f"{path}:unparsable"]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            owner = node.value
            hit = _private(node.attr) and not (
                isinstance(owner, ast.Name) and owner.id in ("self", "cls")
            )
        elif isinstance(node, ast.Call):
            name = node.args[1] if len(node.args) > 1 else None
            hit = (
                isinstance(node.func, ast.Name)
                and node.func.id in _BY_NAME
                and isinstance(name, ast.Constant)
                and isinstance(name.value, str)
                and _private(name.value)
            )
        else:
            hit = False
        if hit:
            found.append(f"{path}:{node.lineno}")
    return found


def _untyped_runners(path: Path) -> list[str]:
    """Each `runner` parameter in `path` not annotated `RunnerPort`, as `file:line`."""
    tree = _parse(path)
    if tree is None:
        return [f"{path}:unparsable"]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.arg == "runner" and (
                    arg.annotation is None or ast.unparse(arg.annotation) != "RunnerPort"
                ):
                    found.append(f"{path}:{node.lineno}")
    return found


def _runner(tmp_path: Path) -> PipelineRunner:
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    pipeline = PipelineDefinition(name="empty", steps=[])
    return PipelineRunner(pipeline, context, registry=StepHandlerRegistry())


def test_no_engine_module_touches_another_objects_private_field() -> None:
    files = sorted(_ENGINE.rglob("*.py"))

    assert files
    assert [hit for f in files for hit in _private_reads(f)] == []


def test_every_runner_parameter_is_a_runner_port() -> None:
    files = sorted(_ENGINE.rglob("*.py"))

    assert [hit for f in files for hit in _untyped_runners(f)] == []


def test_a_fresh_runner_is_a_runner_port_with_no_session(tmp_path: Path) -> None:
    runner = _runner(tmp_path)

    assert isinstance(runner, RunnerPort)
    assert runner.session_active is False
    assert runner.session_kept is False


def test_own_fields_and_dunders_pass(tmp_path: Path) -> None:
    f = tmp_path / "own.py"
    f.write_text("class A:\n    def m(self):\n        return self._x, type(self).__name__\n")

    assert _private_reads(f) == []


def test_every_private_touch_is_found(tmp_path: Path) -> None:
    f = tmp_path / "reach.py"
    f.write_text(
        "def f(runner):\n"
        "    runner._context\n"
        "    getattr(runner, '_session_active', False)\n"
        "    setattr(runner, '_kept', True)\n"
        "    hasattr(runner, '_store')\n"
        "    getattr(runner, 'context')\n"
    )

    assert _private_reads(f) == [f"{f}:{n}" for n in (2, 3, 4, 5)]


def test_an_untyped_or_any_runner_is_found(tmp_path: Path) -> None:
    f = tmp_path / "loose.py"
    f.write_text(
        "def a(runner): ...\n"
        "def b(runner: Any): ...\n"
        "async def c(*, runner: RunnerPort): ...\n"
        "def d(other): ...\n"
    )

    assert _untyped_runners(f) == [f"{f}:1", f"{f}:2"]


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n")

    assert _private_reads(f) == [f"{f}:unparsable"]
    assert _untyped_runners(f) == [f"{f}:unparsable"]
