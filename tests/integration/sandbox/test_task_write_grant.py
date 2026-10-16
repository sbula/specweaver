# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The coder may create and change its task's files and nothing else; a role with no rule, nothing.

Proves: E-SENS-03 FR-2
Proves: E-SENS-03 FR-3
Proves: E-SENS-03 FR-4
Proves: E-SENS-03 NFR-1
Proves: E-SENS-03 NFR-2

Driven through `ToolDispatcher`, the path a model's tool call takes; the code-structure tool, the
executor and the grants are real.

| Bucket | Case |
|---|---|
| Happy | the coder creates `src/greeter.py` and its test, and changes them |
| Boundary | a glob entry `src/app/**` covers a nested file; `doc_updates.md` is writable, as the merge keeps it |
| Degradation | no task files: the coder reads, and every write is refused |
| Hostile | `README.md`, `docs/`, a file beside the task, a delete outside it; `..` or absolute entries; a role with no rule |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_TASK = ["src/greeter.py", "tests/test_greeter.py"]
_CODE = "def greet() -> str:\n    return 'hi'\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "src" / "other.py").write_text("def other() -> int:\n    return 1\n", encoding="utf-8")
    (root / "README.md").write_text("Greeter.\n", encoding="utf-8")
    return root


def _dispatcher(root: Path, task_files: list[str], role: str = "implementer") -> ToolDispatcher:
    return ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[root]), role=role, allowed_tools=["ast"], task_files=task_files
    )


async def _create(dispatcher: ToolDispatcher, path: str) -> dict[str, Any]:
    return await dispatcher.execute("create_module", {"path": path, "code": _CODE})


async def test_the_coder_creates_and_changes_its_task_files(project: Path) -> None:
    dispatcher = _dispatcher(project, _TASK)

    made = [await _create(dispatcher, path) for path in _TASK]
    changed = await dispatcher.execute(
        "replace_symbol_body",
        {"path": "src/greeter.py", "symbol_name": "greet", "new_code": "    return 'hello'\n"},
    )

    assert all("error" not in result for result in made), made
    assert "error" not in changed, changed
    assert "hello" in (project / "src" / "greeter.py").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path", ["src/other_new.py", "README.md", "docs/guide.md", "tests/test_other.py"]
)
async def test_a_create_outside_the_task_is_refused_and_named(project: Path, path: str) -> None:
    result = await _create(_dispatcher(project, _TASK), path)

    assert path in result["error"]
    assert not (project / path).exists() or path == "README.md"
    assert (project / "README.md").read_text(encoding="utf-8") == "Greeter.\n"


async def test_a_change_or_delete_outside_the_task_is_refused(project: Path) -> None:
    dispatcher = _dispatcher(project, _TASK)

    changed = await dispatcher.execute(
        "replace_symbol_body",
        {"path": "src/other.py", "symbol_name": "other", "new_code": "    return 2\n"},
    )
    deleted = await dispatcher.execute("delete_module", {"path": "src/other.py"})

    assert "src/other.py" in changed["error"]
    assert "src/other.py" in deleted["error"]
    assert "return 1" in (project / "src" / "other.py").read_text(encoding="utf-8")


async def test_the_coder_still_reads_the_whole_project(project: Path) -> None:
    result = await _dispatcher(project, _TASK).execute("list_symbols", {"path": "src/other.py"})

    assert "error" not in result, result


async def test_a_glob_entry_covers_a_nested_file(project: Path) -> None:
    result = await _create(_dispatcher(project, ["src/app/**"]), "src/app/deep/greeter.py")

    assert "error" not in result, result
    assert (project / "src" / "app" / "deep" / "greeter.py").exists()


async def test_doc_updates_is_writable_as_the_merge_keeps_it(project: Path) -> None:
    result = await _create(_dispatcher(project, _TASK), "doc_updates.md")

    assert "error" not in result, result


async def test_no_task_files_means_no_write(project: Path) -> None:
    result = await _create(_dispatcher(project, []), "src/greeter.py")

    assert "src/greeter.py" in result["error"]
    assert not (project / "src" / "greeter.py").exists()


@pytest.mark.parametrize("entry", ["../outside.py", "src/../../outside.py", "/etc/passwd", ""])
def test_an_entry_that_escapes_the_project_stops_the_grant(project: Path, entry: str) -> None:
    with pytest.raises(ValueError, match="task file"):
        _dispatcher(project, [entry])


@pytest.mark.parametrize("role", ["drafter", "architect", "someone_new"])
async def test_a_role_with_no_rule_can_do_nothing(project: Path, role: str) -> None:
    grants = ToolDispatcher._compute_role_grants(role, WorkspaceBoundary(roots=[project]), _TASK)

    assert grants == []


@pytest.mark.parametrize("role", ["reviewer", "planner"])
async def test_the_read_only_roles_still_write_nothing(project: Path, role: str) -> None:
    result = await _create(_dispatcher(project, _TASK, role=role), "src/greeter.py")

    assert "error" in result
    assert not (project / "src" / "greeter.py").exists()
