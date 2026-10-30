# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No QA runner, git executor or file search builds its own host executor.

Proves: TECH-087 FR-9

Host or container is the caller's choice. A constructor that quietly builds a host executor when
none is given turns a forgotten container into a host run. This test reads the files with `ast`, so
a new runner that brings the fallback back fails here.

| Bucket | Case |
|---|---|
| Happy | the real runners, the factory, `GitExecutor` and the search have no fallback |
| Boundary | an `or` default and a parameter default both count; a glob covers a new runner |
| Degradation | a file that does not parse fails the check, it is not skipped |
| Hostile | an `or` between two names that are not executors is not a fallback |
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SANDBOX = Path(__file__).resolve().parents[3] / "src" / "specweaver" / "sandbox"
_PARAMETERS = {"executor", "subprocess_executor"}


def _files() -> list[Path]:
    runners = sorted((_SANDBOX / "language" / "core").glob("*/runner.py"))
    return [
        *runners,
        _SANDBOX / "language" / "core" / "runner_factory.py",
        _SANDBOX / "git" / "core" / "executor.py",
        _SANDBOX / "filesystem" / "core" / "search.py",
    ]


def _called_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
    return ""


def _fallbacks(source: str) -> list[str]:
    """Each place `source` builds an executor the caller did not give, by line."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            if any(_called_name(v).endswith("Executor") for v in node.values[1:]):
                found.append(f"{node.lineno}: `or` builds an executor")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            positional = [*args.posonlyargs, *args.args]
            with_default = positional[len(positional) - len(args.defaults) :]
            with_default += [
                a for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True) if d is not None
            ]
            found += [
                f"{node.lineno}: `{node.name}({a.arg}=…)` has a default"
                for a in with_default
                if a.arg in _PARAMETERS
            ]
    return found


def test_no_constructor_builds_its_own_executor() -> None:
    files = _files()
    assert len(files) >= 8, files

    offenders = {
        str(path.relative_to(_SANDBOX)): hits
        for path in files
        if (hits := _fallbacks(path.read_text(encoding="utf-8")))
    }

    assert offenders == {}


@pytest.mark.parametrize(
    "source",
    [
        "def f(cwd, executor=None):\n    pass\n",
        "def f(cwd, *, subprocess_executor=None):\n    pass\n",
        "x = executor or SubprocessExecutor(cwd=cwd)\n",
        "x = executor or mod.ContainerSubprocessExecutor(cwd)\n",
    ],
)
def test_each_fallback_shape_is_found(source: str) -> None:
    assert _fallbacks(source)


@pytest.mark.parametrize(
    "source",
    [
        "def f(cwd, executor):\n    pass\n",
        "def f(cwd, *, executor):\n    pass\n",
        "x = a or b\n",
        "x = name or default_name()\n",
    ],
)
def test_a_required_executor_is_not_a_fallback(source: str) -> None:
    assert _fallbacks(source) == []


def test_a_file_that_does_not_parse_fails() -> None:
    with pytest.raises(SyntaxError):
        _fallbacks("def broken(:\n")
