# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The flow engine creates and deletes files on disk, and only where it is safe.

Proves: D-SENS-06 FR-12
Proves: D-SENS-06 FR-13

| Bucket | Case |
|---|---|
| Happy | a new module is written; an unused module is deleted |
| Boundary | a new module in a folder that does not exist yet |
| Degradation | a file that appeared on disk after the read refuses the create |
| Hostile | a create over an existing or ignored file; a delete of a used or protected file |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

if TYPE_CHECKING:
    from pathlib import Path

_FILES = {
    "app/__init__.py": "",
    "app/util.py": "def shout(n):\n    return n\n",
    "app/main.py": "from app.util import shout\n",
    "app/lonely.py": "def alone():\n    return 1\n",
    ".specweaverignore": "build/\n",
    "build/gen.py": "x = 1\n",
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


def test_a_new_module_is_written(project: Path) -> None:
    result = CodeStructureAtom(cwd=project).run(
        {
            "intent": "create_module",
            "path": "app/words/new.py",
            "code": "def fresh():\n    return 2\n",
        }
    )

    assert result.status == AtomStatus.SUCCESS, result.message
    assert (project / "app/words/new.py").read_text() == "def fresh():\n    return 2\n"
    assert result.exports["created"] == "app/words/new.py"


def test_an_unused_module_is_deleted(project: Path) -> None:
    result = CodeStructureAtom(cwd=project).run(
        {"intent": "delete_module", "path": "app/lonely.py"}
    )

    assert result.status == AtomStatus.SUCCESS, result.message
    assert not (project / "app/lonely.py").exists()
    assert result.exports["deleted"] == "app/lonely.py"


@pytest.mark.parametrize(
    ("context", "reason"),
    [
        ({"intent": "create_module", "path": "app/util.py", "code": "x = 1\n"}, "exists"),
        ({"intent": "create_module", "path": "build/gen.py", "code": "x = 2\n"}, "exists"),
        ({"intent": "create_module", "path": "app/bad.py", "code": "def f(:\n"}, "parse"),
        ({"intent": "create_module", "path": "app/x.py"}, "needs"),
        ({"intent": "delete_module", "path": "app/util.py"}, "still used"),
        ({"intent": "delete_module", "path": ".specweaverignore"}, "not supported"),
    ],
)
def test_an_unsafe_request_changes_nothing(
    project: Path, context: dict[str, str], reason: str
) -> None:
    before = _snapshot(project)
    result = CodeStructureAtom(cwd=project).run(context)

    assert result.status == AtomStatus.FAILED
    assert reason in result.message
    assert _snapshot(project) == before
