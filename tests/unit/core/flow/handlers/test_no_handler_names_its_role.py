# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No flow handler names a model role by hand: a step's role comes from the step table.

Proves: TECH-082 FR-9

A call made for another task may keep its explicit role; it goes into `_ALLOWED` with its reason.

| Bucket | Case |
|---|---|
| Happy | every handler module is clean; a clean file passes |
| Boundary | `TaskType` as a type hint, or only imported, is not a read |
| Degradation | a file that does not parse is named, not skipped |
| Hostile | an aliased `TaskType as T; T.REVIEW` is found; `getattr(TaskType, "REVIEW")` is found |
"""

from __future__ import annotations

import ast
from pathlib import Path

_HANDLERS = (
    Path(__file__).resolve().parents[5] / "src" / "specweaver" / "core" / "flow" / "handlers"
)
#: `file name: reason` for a role read that is a call made for another task.
_ALLOWED: dict[str, str] = {}


def _aliases(tree: ast.Module) -> set[str]:
    """Every local name `TaskType` is imported as."""
    names = {"TaskType"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {a.asname or a.name for a in node.names if a.name == "TaskType"}
    return names


def _role_reads(path: Path) -> list[str]:
    """Each `TaskType.<member>` or `getattr(TaskType, ...)` read in `path`, as `file:line`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # expected: named, so an unreadable file cannot pass as clean
        return [f"{path}:unparsable"]
    names = _aliases(tree)
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in names
        ) or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in names
        ):
            found.append(f"{path}:{node.lineno}")
    return found


def test_no_handler_names_its_role() -> None:
    files = sorted(f for f in _HANDLERS.glob("*.py") if f.name not in _ALLOWED)

    assert files
    assert [hit for f in files for hit in _role_reads(f)] == []


def test_a_clean_file_passes(tmp_path: Path) -> None:
    f = tmp_path / "clean.py"
    f.write_text("async def run(context, step):\n    return llm_for_step(context, step)\n")

    assert _role_reads(f) == []


def test_a_type_hint_or_an_import_is_not_a_read(tmp_path: Path) -> None:
    f = tmp_path / "hint.py"
    f.write_text(
        "from specweaver.infrastructure.llm.models import TaskType\n\n\n"
        "def pick(task_type: TaskType) -> TaskType:\n    return task_type\n"
    )

    assert _role_reads(f) == []


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n")

    assert _role_reads(f) == [f"{f}:unparsable"]


def test_an_aliased_read_is_found(tmp_path: Path) -> None:
    f = tmp_path / "alias.py"
    f.write_text(
        "def run(c):\n    from x.models import TaskType as _T\n    return llm_for(c, _T.REVIEW)\n"
    )

    assert _role_reads(f) == [f"{f}:3"]


def test_a_getattr_read_is_found(tmp_path: Path) -> None:
    f = tmp_path / "sneaky.py"
    f.write_text("def run(c):\n    return llm_for(c, getattr(TaskType, 'REVIEW'))\n")

    assert _role_reads(f) == [f"{f}:2"]
