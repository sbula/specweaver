# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The flow engine renames a Python symbol on disk: every file, or none.

Proves: D-SENS-06 FR-3
Proves: D-SENS-06 FR-4
Proves: D-SENS-06 NFR-1

A real project in a temporary folder, a real `FileExecutor` and the real parsers. The atom reads
the project, plans the rename, and writes through the executor. It checks no grant; it still
refuses protected files.

| Bucket | Case |
|---|---|
| Happy | a function renamed in three files; a README mention reported |
| Boundary | ignored folders and links are not read; 500 files under 30 s |
| Degradation | a write fails midway, a restore fails, a file changes after the plan |
| Hostile | a protected file in the plan, `../`, a missing field, a TypeScript file |
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.code_structure.core import changes
from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
from specweaver.sandbox.filesystem.core.executor import ExecutorResult, FileExecutor

if TYPE_CHECKING:
    from pathlib import Path

_FILES = {
    "app/__init__.py": "",
    "app/billing.py": "def total(a, b):\n    return a + b\n",
    "app/main.py": "from app.billing import total\n\nprint(total(1, 2))\n",
    "app/report.py": "import app.billing as bill\n\nx = bill.total(1, 2)\n",
    "README.md": "Call total to add.\n",
}


def _project(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _rename(
    atom: CodeStructureAtom,
    symbol: str = "total",
    new: str = "sum_up",
    path: str = "app/billing.py",
):  # type: ignore[no-untyped-def]
    return atom.run(
        {"intent": "rename_symbol", "path": path, "symbol_name": symbol, "new_name": new}
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return _project(tmp_path / "project", _FILES)


# --- Happy -----------------------------------------------------------------------------------


def test_a_function_is_renamed_in_every_file(project: Path) -> None:
    result = _rename(CodeStructureAtom(cwd=project))

    assert result.status == AtomStatus.SUCCESS, result.message
    assert (
        project / "app/main.py"
    ).read_text() == "from app.billing import sum_up\n\nprint(sum_up(1, 2))\n"
    assert (project / "app/report.py").read_text().endswith("bill.sum_up(1, 2)\n")
    assert (project / "app/billing.py").read_text().startswith("def sum_up(a, b):")
    assert result.exports["changed"] == ["app/billing.py", "app/main.py", "app/report.py"]
    assert result.exports["mentions"] == ["README.md:1"]
    assert (project / "README.md").read_text() == "Call total to add.\n"


def test_an_unsure_use_changes_no_file(project: Path) -> None:
    (project / "app/zz.py").write_text("def f(o):\n    return o.total()\n", encoding="utf-8")
    before = _snapshot(project)

    result = _rename(CodeStructureAtom(cwd=project))

    assert result.status == AtomStatus.FAILED
    assert "app/zz.py:2" in result.message
    assert result.exports["spots"] == ["app/zz.py:2"]
    assert _snapshot(project) == before


# --- Boundary --------------------------------------------------------------------------------


def test_ignored_folders_and_links_are_not_read(project: Path, tmp_path: Path) -> None:
    unsure = "def f(o):\n    return o.total()\n"
    _project(
        project, {".venv/lib/x.py": unsure, "build/y.py": unsure, ".specweaverignore": "build/\n"}
    )
    outside = _project(tmp_path / "outside", {"z.py": unsure})
    (project / "linked").symlink_to(outside, target_is_directory=True)

    result = _rename(CodeStructureAtom(cwd=project))

    assert result.status == AtomStatus.SUCCESS, result.message
    assert (outside / "z.py").read_text() == unsure


def test_an_engine_exclusion_is_not_read(project: Path) -> None:
    _project(project, {"vendor/x.py": "def f(o):\n    return o.total()\n"})
    atom = CodeStructureAtom(cwd=project, exclude_dirs={"vendor"})
    assert _rename(atom).status == AtomStatus.SUCCESS


def test_500_files_rename_in_under_30_seconds(tmp_path: Path) -> None:
    files = {
        "app/__init__.py": "",
        "app/billing.py": "def total(a, b):\n    return a + b\n",
        **{
            f"app/m{n}.py": f"from app.billing import total\n\n\ndef f{n}(x):\n    # adds\n    return total(x, {n})\n"
            for n in range(500)
        },
    }
    root = _project(tmp_path / "big", files)

    started = time.monotonic()
    result = _rename(CodeStructureAtom(cwd=root))
    elapsed = time.monotonic() - started

    assert result.status == AtomStatus.SUCCESS, result.message
    assert len(result.exports["changed"]) == 501
    assert elapsed < 30, elapsed


# --- Degradation -----------------------------------------------------------------------------


class _FailingWrites(FileExecutor):
    """Fails the `fail_on`-th write and every write after `fail_after`, if set."""

    def __init__(self, cwd: Path, fail_on: int, fail_after: int | None = None) -> None:
        super().__init__(cwd)
        self.writes = 0
        self.fail_on = fail_on
        self.fail_after = fail_after

    def write(self, path: str, content: str) -> ExecutorResult:
        self.writes += 1
        if self.writes == self.fail_on or (self.fail_after and self.writes > self.fail_after):
            return ExecutorResult(status="error", error="disk full")
        return super().write(path, content)


def test_a_write_that_fails_midway_restores_the_others(project: Path) -> None:
    before = _snapshot(project)

    result = _rename(CodeStructureAtom(file_executor=_FailingWrites(project, fail_on=2)))

    assert result.status == AtomStatus.FAILED
    assert "disk full" in result.message
    assert _snapshot(project) == before
    assert not list(project.rglob("*.tmp.*"))


def test_a_restore_that_fails_is_named(project: Path) -> None:
    result = _rename(
        CodeStructureAtom(file_executor=_FailingWrites(project, fail_on=2, fail_after=2))
    )

    assert result.status == AtomStatus.FAILED
    assert "app/billing.py" in result.message
    assert result.exports["unrestored"] == ["app/billing.py"]


def test_a_file_changed_after_the_plan_refuses(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_plan = changes.plan_rename

    def plan_then_edit(*args, **kwargs):  # type: ignore[no-untyped-def]
        plan = real_plan(*args, **kwargs)
        (project / "app/main.py").write_text("# edited meanwhile\n", encoding="utf-8")
        return plan

    monkeypatch.setattr(changes, "plan_rename", plan_then_edit)
    result = _rename(CodeStructureAtom(cwd=project))

    assert result.status == AtomStatus.FAILED
    assert "app/main.py" in result.message
    assert (project / "app/billing.py").read_text().startswith("def total")


# --- Hostile ---------------------------------------------------------------------------------


@pytest.mark.parametrize("hook", [".env/hook.py", "zz/.env/hook.py"])
def test_a_protected_file_in_the_plan_is_refused_before_any_write(project: Path, hook: str) -> None:
    _project(project, {hook: "from app.billing import total\ntotal(1, 2)\n"})
    before = _snapshot(project)
    executor = _FailingWrites(project, fail_on=0)

    result = _rename(CodeStructureAtom(file_executor=executor))

    assert result.status == AtomStatus.FAILED
    assert hook in result.message
    assert executor.writes == 0
    assert _snapshot(project) == before


@pytest.mark.parametrize(
    "context",
    [
        {"path": "../outside.py", "symbol_name": "total", "new_name": "x"},
        {"path": "app/billing.py", "new_name": "x"},
        {"path": "app/billing.py", "symbol_name": "total"},
        {"path": "app/billing.py", "symbol_name": "total", "new_name": None},
    ],
)
def test_a_bad_request_changes_nothing(project: Path, context: dict[str, object]) -> None:
    before = _snapshot(project)
    result = CodeStructureAtom(cwd=project).run({"intent": "rename_symbol", **context})

    assert result.status == AtomStatus.FAILED
    assert _snapshot(project) == before


def test_a_sql_file_is_refused(project: Path) -> None:
    _project(project, {"db/a.sql": "CREATE TABLE total (id INT);\n"})
    result = _rename(CodeStructureAtom(cwd=project), path="db/a.sql")
    assert result.status == AtomStatus.FAILED
    assert "not supported" in result.message
