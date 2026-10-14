# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The flow engine moves a file on disk and rewrites its imports: every file, or none.

Proves: D-SENS-06 FR-10
Proves: D-SENS-06 FR-11

A real project in a temporary folder and a real `FileExecutor`.

| Bucket | Case |
|---|---|
| Happy | a Python module moved; importers rewritten; the old file gone |
| Boundary | a move into a new folder that does not exist yet |
| Degradation | a write that fails midway restores everything and keeps the old file |
| Hostile | a protected target, a target under another `context.yaml`, a target that exists |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
from specweaver.sandbox.filesystem.core.executor import ExecutorResult, FileExecutor

if TYPE_CHECKING:
    from pathlib import Path

_FILES = {
    "context.yaml": "name: root\n",
    "app/__init__.py": "",
    "app/greeter.py": "def greet(n):\n    return n\n",
    "app/main.py": "from app.greeter import greet\n\nprint(greet('a'))\n",
    "lib/context.yaml": "name: lib\n",
}


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _move(atom: CodeStructureAtom, new: str, path: str = "app/greeter.py"):  # type: ignore[no-untyped-def]
    return atom.run({"intent": "move_module", "path": path, "new_path": new})


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return _write(tmp_path / "project", _FILES)


def test_a_module_moves_and_its_importers_follow(project: Path) -> None:
    result = _move(CodeStructureAtom(cwd=project), "app/words/hello.py")

    assert result.status == AtomStatus.SUCCESS, result.message
    assert not (project / "app/greeter.py").exists()
    assert (project / "app/words/hello.py").read_text() == "def greet(n):\n    return n\n"
    assert (project / "app/main.py").read_text().startswith("from app.words.hello import greet\n")
    assert result.exports["moved"] == ["app/greeter.py", "app/words/hello.py"]
    assert result.exports["changed"] == ["app/main.py", "app/words/hello.py"]


class _FailingWrites(FileExecutor):
    def __init__(self, cwd: Path, fail_on: int) -> None:
        super().__init__(cwd)
        self.writes = 0
        self.fail_on = fail_on

    def write(self, path: str, content: str) -> ExecutorResult:
        self.writes += 1
        if self.writes == self.fail_on:
            return ExecutorResult(status="error", error="disk full")
        return super().write(path, content)


@pytest.mark.parametrize("fail_on", [1, 2])
def test_a_failed_write_restores_everything(project: Path, fail_on: int) -> None:
    before = _snapshot(project)
    result = _move(
        CodeStructureAtom(file_executor=_FailingWrites(project, fail_on)), "app/words/hello.py"
    )

    assert result.status == AtomStatus.FAILED
    assert "disk full" in result.message
    assert _snapshot(project) == before
    assert not (project / "app/words").exists() or not any((project / "app/words").iterdir())


@pytest.mark.parametrize(
    ("new", "reason"),
    [
        (".env/greeter.py", "protected"),
        ("lib/greeter.py", "module"),
        ("app/main.py", "exists"),
        ("../greeter.py", "outside"),
    ],
)
def test_a_bad_target_changes_nothing(project: Path, new: str, reason: str) -> None:
    before = _snapshot(project)
    result = _move(CodeStructureAtom(cwd=project), new)

    assert result.status == AtomStatus.FAILED
    assert reason in result.message
    assert _snapshot(project) == before


def test_a_missing_field_changes_nothing(project: Path) -> None:
    before = _snapshot(project)
    result = CodeStructureAtom(cwd=project).run({"intent": "move_module", "path": "app/greeter.py"})
    assert result.status == AtomStatus.FAILED
    assert _snapshot(project) == before


class _FailingDelete(FileExecutor):
    def delete(self, path: str) -> ExecutorResult:
        if path == "app/greeter.py":
            return ExecutorResult(status="error", error="locked")
        return super().delete(path)


def test_a_failed_delete_of_the_old_file_removes_the_new_one(project: Path) -> None:
    before = _snapshot(project)
    result = _move(CodeStructureAtom(file_executor=_FailingDelete(project)), "app/words/hello.py")

    assert result.status == AtomStatus.FAILED
    assert "locked" in result.message
    assert _snapshot(project) == before
