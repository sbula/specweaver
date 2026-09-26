# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The agent's AST tool works on project files, and cannot write the files that bound it.

Proves: TECH-072 FR-1, FR-5

Driven through `ToolDispatcher.execute`, the path an agent's tool call takes: the dispatcher's
grants, the tool's grant matcher, the atom and the executor it is built on are all real. Paths are
relative to the project root, as the tool definitions tell the model to send them.

| Bucket | Case |
|---|---|
| Happy | `read_file_structure` and `replace_symbol` on `src/main.py` work |
| Boundary | a protected directory nested below the root (`.specweaver/scripts/`) |
| Degradation | a refusal reaches the agent as an error, not as "Replaced symbol" |
| Hostile | `.specweaver/`, `.git/`, `.env/` targets refused and unchanged, relative or absolute; `../` escape refused |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

_ORIGINAL = "def hook():\n    return 'original'\n"
_REPLACEMENT = "def hook():\n    return 'rewritten by the agent'\n"


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text(_ORIGINAL, encoding="utf-8")
    for protected in (".specweaver/scripts", ".git/hooks", ".env"):
        (root / protected).mkdir(parents=True)
        (root / protected / "hook.py").write_text(_ORIGINAL, encoding="utf-8")
    (tmp_path / "outside.py").write_text(_ORIGINAL, encoding="utf-8")
    return root


def _implementer(project: Path) -> ToolDispatcher:
    boundary = WorkspaceBoundary(roots=[project])
    return ToolDispatcher.create_standard_set(boundary, role="implementer", allowed_tools=["ast"])


def _replace(path: str) -> dict:
    return {"path": path, "symbol_name": "hook", "new_code": _REPLACEMENT}


class TestTheAgentAstToolWorks:
    async def test_a_source_file_can_be_read(self, project: Path) -> None:
        result = await _implementer(project).execute("read_file_structure", {"path": "src/main.py"})

        assert "error" not in result, result
        assert "hook" in str(result)

    async def test_a_source_file_can_be_rewritten(self, project: Path) -> None:
        result = await _implementer(project).execute("replace_symbol", _replace("src/main.py"))

        assert "error" not in result, result
        assert "rewritten by the agent" in (project / "src" / "main.py").read_text()


class TestTheAgentAstToolRespectsItsBoundary:
    @pytest.mark.parametrize(
        "target",
        [".specweaver/scripts/hook.py", ".git/hooks/hook.py", ".env/hook.py"],
    )
    async def test_a_protected_path_is_refused_and_left_unchanged(
        self, project: Path, target: str
    ) -> None:
        result = await _implementer(project).execute("replace_symbol", _replace(target))

        assert "error" in result, f"agent was told the write succeeded: {result}"
        assert (project / target).read_text(encoding="utf-8") == _ORIGINAL

    async def test_a_path_escaping_the_root_is_refused(self, project: Path) -> None:
        result = await _implementer(project).execute("replace_symbol", _replace("../outside.py"))

        assert "error" in result
        assert (project.parent / "outside.py").read_text(encoding="utf-8") == _ORIGINAL

    async def test_an_absolute_path_to_a_protected_file_is_refused(self, project: Path) -> None:
        target = project / ".env" / "hook.py"

        result = await _implementer(project).execute("replace_symbol", _replace(str(target)))

        assert "error" in result
        assert target.read_text(encoding="utf-8") == _ORIGINAL
