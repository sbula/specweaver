# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each flow name means one thing: no dead names, no two modules with one title, no private import
from outside the handlers.

Proves: TECH-082 FR-12

| Bucket | Case |
|---|---|
| Happy | `roles_of` is importable from the public `handlers.roles`; the assemblers carry distinct titles |
| Boundary | the generation handlers keep their other class settings, only `FILENAME_PREFIX` goes |
| Degradation | a file that does not parse is named by the import scan, not skipped |
| Hostile | the old `context_assembler` path does not import (no shim); `import ..._llm` is found too |
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from specweaver.core.flow.handlers.generation import GenerateCodeHandler, GenerateTestsHandler

_SRC = Path(__file__).resolve().parents[4] / "src" / "specweaver"
_HANDLERS = _SRC / "core" / "flow" / "handlers"
_PRIVATE = "specweaver.core.flow.handlers._llm"


def _title(module: str) -> str:
    doc = importlib.import_module(module).__doc__ or ""
    return doc.split("—")[0].strip()


def _private_imports(path: Path) -> list[str]:
    """Each import of the handlers' private `_llm` module in `path`, as `file:line`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # expected: named, so an unreadable file cannot pass as clean
        return [f"{path}:unparsable"]
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.ImportFrom) and node.module == _PRIVATE) or (
            isinstance(node, ast.Import) and any(a.name == _PRIVATE for a in node.names)
        ):
            found.append(f"{path}:{node.lineno}")
    return found


@pytest.mark.parametrize("handler", [GenerateCodeHandler, GenerateTestsHandler])
def test_the_generation_handlers_have_no_filename_prefix(handler: type) -> None:
    assert not hasattr(handler, "FILENAME_PREFIX")
    assert handler.OUTPUT_SUBDIR


def test_the_old_assembler_path_does_not_import() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("specweaver.core.flow.handlers.context_assembler")


def test_the_two_assemblers_have_distinct_titles() -> None:
    skeleton = _title("specweaver.core.flow.handlers.skeleton_assembler")
    mcp = _title("specweaver.core.flow.handlers.mcp_assembler")

    assert (skeleton, mcp) == ("Skeleton assembler", "MCP resource assembler")


def test_roles_of_has_a_public_home() -> None:
    from specweaver.core.flow.handlers.roles import roles_of

    assert callable(roles_of)


def test_nothing_outside_the_handlers_imports_their_private_llm_module() -> None:
    files = sorted(f for f in _SRC.rglob("*.py") if _HANDLERS not in f.parents)

    assert files
    assert [hit for f in files for hit in _private_imports(f)] == []


def test_both_import_forms_are_found(tmp_path: Path) -> None:
    f = tmp_path / "importer.py"
    f.write_text(f"from {_PRIVATE} import roles_of\nimport {_PRIVATE}\nimport os\n")

    assert _private_imports(f) == [f"{f}:1", f"{f}:2"]


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n")

    assert _private_imports(f) == [f"{f}:unparsable"]
