# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The file tool and the AST tool give the same grant verdict for the same path.

Proves: TECH-072 FR-6

The AST tool carried a copy of the file tool's matcher ("identical to FileSystemTool logic") that
had drifted: it prefixed relative paths with `/` instead of resolving them against the project root,
so no relative path ever matched a dispatcher grant.

| Bucket | Case |
|---|---|
| Happy | a file inside the granted folder |
| Boundary | the granted folder itself; `src/../src/x` normalised back inside; the project root (`""`, `.`) outside a `src/` grant |
| Degradation | a sibling folder with no grant |
| Hostile | `../` escaping the root; a prefix-lookalike folder (`src2/`) |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.code_structure.interfaces.tool import CodeStructureTool
from specweaver.sandbox.filesystem.core.executor import FileExecutor
from specweaver.sandbox.filesystem.interfaces.tool import FileSystemTool
from specweaver.sandbox.security import AccessMode, FolderGrant

if TYPE_CHECKING:
    from pathlib import Path

_PATHS = [
    ("src/main.py", True),
    ("src", True),
    ("src/../src/main.py", True),
    ("docs/readme.md", False),
    ("../outside.py", False),
    ("src2/x.py", False),
    ("", False),
    (".", False),
]


@pytest.fixture()
def tools(tmp_path: Path) -> tuple[FileSystemTool, CodeStructureTool]:
    (tmp_path / "src").mkdir()
    grants = [FolderGrant(str(tmp_path / "src"), AccessMode.FULL, recursive=True)]
    fs_tool = FileSystemTool(FileExecutor(tmp_path), role="implementer", grants=grants)
    atom = MagicMock()
    atom.cwd = tmp_path.resolve()
    ast_tool = CodeStructureTool(atom=atom, role="implementer", grants=grants)
    return fs_tool, ast_tool


@pytest.mark.parametrize(("path", "covered"), _PATHS)
def test_both_tools_agree(
    tools: tuple[FileSystemTool, CodeStructureTool], path: str, covered: bool
) -> None:
    fs_tool, ast_tool = tools
    modes = frozenset({AccessMode.READ, AccessMode.WRITE, AccessMode.FULL})

    fs_allows = fs_tool._check_grant(path, modes) is None
    ast_allows = ast_tool._check_grant(path, modes) is None

    assert fs_allows is covered, f"file tool: {path}"
    assert ast_allows is fs_allows, f"AST tool disagrees with the file tool on {path}"
