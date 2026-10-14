# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A change takes only safe paths, writes in path order, and leaves no temporary file.

Proves: D-SENS-06 NFR-2
Proves: D-SENS-06 NFR-4
Proves: D-SENS-06 NFR-5

The Atom, which checks no grant, so the path checks themselves are what refuses. A real project in
a temporary folder and a real `FileExecutor`.

| Bucket | Case |
|---|---|
| Happy | a rename writes its three files in sorted path order |
| Boundary | a move writes the new file in the same order as the others |
| Degradation | the disk fails inside a write: no temporary file stays, every file is restored |
| Hostile | `..`, an absolute path, a `:` stream, a symlink out of or inside the project |
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
from specweaver.sandbox.filesystem.core import executor as executor_module
from specweaver.sandbox.filesystem.core.executor import ExecutorResult, FileExecutor

if TYPE_CHECKING:
    from pathlib import Path

_FILES = {
    "app/__init__.py": "",
    "app/billing.py": "def total(a, b):\n    return a + b\n",
    "app/main.py": "from app.billing import total\n\nprint(total(1, 2))\n",
    "app/report.py": "from app.billing import total\n\nx = total(1, 2)\n",
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    for rel, text in _FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _rename(path: str = "app/billing.py") -> dict[str, str]:
    return {"intent": "rename_symbol", "path": path, "symbol_name": "total", "new_name": "sum_up"}


def _move(new_path: str) -> dict[str, str]:
    return {"intent": "move_module", "path": "app/billing.py", "new_path": new_path}


# --- NFR-2: safe paths -----------------------------------------------------------------------


@pytest.fixture
def linked(project: Path, tmp_path: Path) -> Path:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "billing.py").write_text(_FILES["app/billing.py"], encoding="utf-8")
    (project / "out").symlink_to(outside, target_is_directory=True)
    (project / "app/alias.py").symlink_to(project / "app/billing.py")
    (project / "inner").symlink_to(project / "app", target_is_directory=True)
    return outside


@pytest.mark.parametrize(
    "context",
    [
        _rename("../outside/billing.py"),
        _rename("/etc/billing.py"),
        _rename("app/billing.py:stream"),
        _rename("app/alias.py"),
        _rename("out/billing.py"),
        _move("../moved.py"),
        _move("/tmp/moved.py"),
        _move("app/moved.py:stream"),
        _move("out/moved.py"),
        _move("inner/moved.py"),
        {"intent": "create_module", "path": "../new.py", "code": "x = 1\n"},
        {"intent": "create_module", "path": "app/new.py:stream", "code": "x = 1\n"},
        {"intent": "create_module", "path": "out/new.py", "code": "x = 1\n"},
        {"intent": "create_module", "path": "inner/new.py", "code": "x = 1\n"},
        {"intent": "delete_module", "path": "out/billing.py"},
        {
            "intent": "replace_symbol_doc",
            "path": "out/billing.py",
            "symbol_name": "total",
            "doc": "x",
        },
    ],
    ids=lambda c: f"{c['intent']}:{c.get('new_path', c['path'])}",
)
def test_an_unsafe_path_changes_nothing(
    project: Path, linked: Path, context: dict[str, str]
) -> None:
    before, outside_before = _snapshot(project), _snapshot(linked)

    result = CodeStructureAtom(cwd=project).run(context)

    assert result.status == AtomStatus.FAILED
    assert _snapshot(project) == before
    assert _snapshot(linked) == outside_before
    assert not (project.parent / "moved.py").exists()
    assert not (project.parent / "new.py").exists()


# --- NFR-4: path order -----------------------------------------------------------------------


class _Recording(FileExecutor):
    def __init__(self, cwd: Path) -> None:
        super().__init__(cwd)
        self.writes: list[str] = []

    def write(self, path: str, content: str) -> ExecutorResult:
        self.writes.append(path)
        return super().write(path, content)


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (_rename(), ["app/billing.py", "app/main.py", "app/report.py"]),
        (_move("app/zz/billing.py"), ["app/main.py", "app/report.py", "app/zz/billing.py"]),
    ],
)
def test_files_are_written_in_path_order(
    project: Path, context: dict[str, str], expected: list[str]
) -> None:
    executor = _Recording(project)
    result = CodeStructureAtom(file_executor=executor).run(context)

    assert result.status == AtomStatus.SUCCESS, result.message
    assert executor.writes == expected


# --- NFR-5: no litter ------------------------------------------------------------------------


@pytest.mark.parametrize("context", [_rename(), _move("app/zz/billing.py")])
def test_a_disk_failure_inside_a_write_leaves_no_temporary_file(
    project: Path, monkeypatch: pytest.MonkeyPatch, context: dict[str, str]
) -> None:
    before = _snapshot(project)
    real_replace = os.replace
    calls = {"n": 0}

    def failing_replace(src: str, dst: str) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        real_replace(src, dst)

    monkeypatch.setattr(executor_module.os, "replace", failing_replace)
    result = CodeStructureAtom(cwd=project).run(context)

    assert result.status == AtomStatus.FAILED
    assert "disk full" in result.message
    assert calls["n"] >= 2
    assert not [p for p in project.rglob("*") if ".tmp." in p.name]
    assert _snapshot(project) == before
