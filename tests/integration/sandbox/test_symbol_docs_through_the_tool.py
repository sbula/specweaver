# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An agent reads and replaces the doc above a symbol through its tool, on disk.

Proves: D-SENS-06 FR-14

Driven through `ToolDispatcher`, the path a model's tool call takes, and through the Atom for the
flow engine. The executor and the parsers are real.

| Bucket | Case |
|---|---|
| Happy | read a Go doc; replace a Python docstring; only the doc's lines change |
| Boundary | a method named without its class; an empty doc removes it |
| Degradation | a doc that would break parsing writes nothing |
| Hostile | SQL; a path outside the write grants; a role that may not write |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
from specweaver.sandbox.code_structure.interfaces.tool import CodeStructureTool
from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.filesystem.core.executor import FileExecutor
from specweaver.sandbox.security import AccessMode, FolderGrant, WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

_FILES = {
    "app/calc.py": 'class Calc:\n    def total(self, a):\n        """Old."""\n        return a\n',
    "app/m.go": "package m\n\n// Total adds.\nfunc Total(a int) int {\n\treturn a\n}\n",
    "db/t.sql": "CREATE TABLE t (id INT);\n",
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    for rel, text in _FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _dispatcher(root: Path, role: str = "implementer") -> ToolDispatcher:
    return ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[root]), role=role, allowed_tools=["ast"]
    )


async def test_the_implementer_reads_a_doc(project: Path) -> None:
    result = await _dispatcher(project).execute(
        "read_symbol_doc", {"path": "app/m.go", "symbol_name": "Total"}
    )
    assert result["doc"] == "Total adds."


async def test_the_implementer_replaces_a_docstring(project: Path) -> None:
    result = await _dispatcher(project).execute(
        "replace_symbol_doc", {"path": "app/calc.py", "symbol_name": "total", "doc": "Sums a."}
    )
    assert "error" not in result, result
    assert (project / "app/calc.py").read_text() == _FILES["app/calc.py"].replace("Old.", "Sums a.")


def test_the_atom_removes_a_doc(project: Path) -> None:
    result = CodeStructureAtom(cwd=project).run(
        {"intent": "replace_symbol_doc", "path": "app/m.go", "symbol_name": "Total", "doc": ""}
    )
    assert result.status == AtomStatus.SUCCESS, result.message
    assert (project / "app/m.go").read_text() == _FILES["app/m.go"].replace("// Total adds.\n", "")


@pytest.mark.parametrize(
    ("intent", "context"),
    [
        ("replace_symbol_doc", {"path": "db/t.sql", "symbol_name": "t", "doc": "x"}),
        ("read_symbol_doc", {"path": "db/t.sql", "symbol_name": "t"}),
        ("replace_symbol_doc", {"path": "app/calc.py", "symbol_name": "total", "doc": 'a """ b'}),
        ("replace_symbol_doc", {"path": "app/calc.py", "symbol_name": "nothing", "doc": "x"}),
        ("replace_symbol_doc", {"path": "app/calc.py", "doc": "x"}),
    ],
)
def test_a_doc_that_cannot_be_written_changes_nothing(
    project: Path, intent: str, context: dict[str, str]
) -> None:
    result = CodeStructureAtom(cwd=project).run({"intent": intent, **context})
    assert result.status == AtomStatus.FAILED
    assert [(project / p).read_text() for p in _FILES] == list(_FILES.values())


def test_a_doc_that_breaks_parsing_writes_nothing(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure

    monkeypatch.setattr(
        GoCodeStructure, "replace_symbol_doc", lambda self, code, name, doc: code + "func ("
    )
    result = CodeStructureAtom(cwd=project).run(
        {"intent": "replace_symbol_doc", "path": "app/m.go", "symbol_name": "Total", "doc": "x"}
    )
    assert result.status == AtomStatus.FAILED
    assert "does not parse" in result.message
    assert (project / "app/m.go").read_text() == _FILES["app/m.go"]


def test_a_read_only_path_refuses_the_replace(project: Path) -> None:
    executor = FileExecutor(project)
    tool = CodeStructureTool(
        CodeStructureAtom(executor),
        "implementer",
        [FolderGrant(str(project), AccessMode.READ, recursive=True)],
        executor=executor,
    )
    assert tool.read_symbol_doc("app/m.go", "Total").data["doc"] == "Total adds."
    assert tool.replace_symbol_doc("app/m.go", "Total", "x").status == "error"
    assert (project / "app/m.go").read_text() == _FILES["app/m.go"]


@pytest.mark.parametrize("role", ["reviewer", "planner", "drafter"])
def test_no_other_role_may_replace_a_doc(project: Path, role: str) -> None:
    names = {d.name for d in _dispatcher(project, role).available_tools()}
    assert "replace_symbol_doc" not in names


def test_the_implementer_is_offered_both(project: Path) -> None:
    names = {d.name for d in _dispatcher(project).available_tools()}
    assert {"read_symbol_doc", "replace_symbol_doc"} <= names
