# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An agent's file tools never give it a file outside the project.

Proves: E-SENS-01 FR-1
Proves: E-SENS-01 FR-2
Proves: E-SENS-01 FR-3

The tools are built the way `sw review` builds them (`ToolDispatcher.create_standard_set`) and
called through `execute`, the one entry a model's tool call takes. Real files, real symlinks.

| Bucket | Case |
|---|---|
| Happy | a project file is read, listed, found and grepped |
| Boundary | a model is offered the four read tools and nothing else |
| Degradation | a refused path is an error the model sees, not an empty success |
| Hostile | `../`, an absolute path, a symlinked file, a symlinked folder |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

_SECRET = "TOPSECRET"
_ROLES = ["reviewer", "implementer"]


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text(_SECRET, encoding="utf-8")
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "src" / "own.py").write_text("x = 1\n", encoding="utf-8")
    (project / "src" / "link.txt").symlink_to(outside / "secret.txt")
    (project / "src" / "linkdir").symlink_to(outside, target_is_directory=True)
    (project / "linkroot").symlink_to(outside, target_is_directory=True)
    return {"project": project, "outside": outside}


def _dispatcher(project: Path, role: str) -> ToolDispatcher:
    return ToolDispatcher.create_standard_set(
        WorkspaceBoundary([project]), role=role, allowed_tools=["fs"]
    )


async def _call(project: Path, role: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return await _dispatcher(project, role).execute(name, args)


@pytest.mark.parametrize("role", _ROLES)
def test_a_model_is_offered_only_the_read_tools(world: dict[str, Path], role: str) -> None:
    names = {d.name for d in _dispatcher(world["project"], role).available_tools()}

    assert names == {"read_file", "list_directory", "grep", "find_files"}


@pytest.mark.parametrize("role", _ROLES)
async def test_the_project_is_readable(world: dict[str, Path], role: str) -> None:
    read = await _call(world["project"], role, "read_file", {"path": "src/own.py"})
    listed = await _call(world["project"], role, "list_directory", {"path": "src"})
    grepped = await _call(world["project"], role, "grep", {"path": ".", "pattern": "x = 1"})
    found = await _call(world["project"], role, "find_files", {"path": ".", "pattern": "*.py"})

    assert read == {"result": "x = 1\n"}
    assert "own.py" in json.dumps(listed)
    assert "own.py" in json.dumps(grepped)
    assert "own.py" in json.dumps(found)


def _escapes(outside: Path) -> list[tuple[str, dict[str, Any]]]:
    return [
        ("read_file", {"path": "../outside/secret.txt"}),
        ("read_file", {"path": str(outside / "secret.txt")}),
        ("read_file", {"path": "src/link.txt"}),
        ("read_file", {"path": "src/linkdir/secret.txt"}),
        ("list_directory", {"path": "src/linkdir"}),
        ("list_directory", {"path": ".."}),
        ("grep", {"path": "linkroot", "pattern": _SECRET}),
        ("grep", {"path": "..", "pattern": _SECRET}),
        ("find_files", {"path": "linkroot", "pattern": "*"}),
        ("find_files", {"path": "..", "pattern": "*"}),
    ]


@pytest.mark.parametrize("role", _ROLES)
@pytest.mark.parametrize("escape", range(10))
async def test_every_way_out_is_refused(world: dict[str, Path], role: str, escape: int) -> None:
    name, args = _escapes(world["outside"])[escape]

    result = await _call(world["project"], role, name, args)

    assert "error" in result, f"{name}({args}) succeeded: {result}"
    assert _SECRET not in json.dumps(result)


@pytest.mark.parametrize("role", _ROLES)
async def test_a_whole_project_search_skips_links_out(world: dict[str, Path], role: str) -> None:
    grepped = await _call(world["project"], role, "grep", {"path": ".", "pattern": _SECRET})
    found = await _call(world["project"], role, "find_files", {"path": ".", "pattern": "*secret*"})

    assert grepped == {"results": []}
    assert found == {"results": []}


async def test_a_link_inside_the_project_cannot_widen_a_grant(world: dict[str, Path]) -> None:
    """The scenario agent reads `specs/` and `contracts/` only; a link to `src/` fails."""
    project = world["project"]
    (project / "specs").mkdir(exist_ok=True)
    (project / "specs" / "own.py").symlink_to(project / "src" / "own.py")

    direct = await _call(project, "scenario_agent", "read_file", {"path": "src/own.py"})
    linked = await _call(project, "scenario_agent", "read_file", {"path": "specs/own.py"})

    assert "error" in direct
    assert "error" in linked, f"a link widened the grant: {linked}"
