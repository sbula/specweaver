# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The AST-to-graph seam carries the dependencies the mapper needs, not just names.

Proves: TECH-068 FR-5

`extract_ast_dict` emitted `{"type", "name"}` per symbol and nothing else, so the mapper had no
import, no base type and no call site to build an edge from. That is why the graph declared nine
edge kinds and wrote one — the mapper could not have done otherwise.

The contract widens ONCE here, per `AD-1`. Imports, supertypes and call sites are all declared now
and only imports are populated, so `SF-03` and `SF-04` fill fields rather than reshape the payload,
and can run in parallel. `B-SENS-08` inherits the same contract instead of repeating this work.

The tier is integration: the adapter's claim is about what the parsers give it, which is a seam.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from pathlib import Path


def _write(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_a_files_imports_reach_the_seam(tmp_path: Path) -> None:
    """Happy path: what `extract_imports` found is what the mapper receives."""
    path = _write(tmp_path, "m.py", "import os\nfrom a.b import C\n\ndef f():\n    pass\n")
    assert extract_ast_dict(path)["imports"] == ["a.b", "os"]


def test_a_relative_import_reaches_the_seam_as_its_module(tmp_path: Path) -> None:
    """The CB-1 correction has to survive the whole way to the mapper, not just the parser."""
    path = _write(tmp_path, "m.py", "from .sibling import X\n")
    assert extract_ast_dict(path)["imports"] == [".sibling"]


def test_a_file_with_no_imports_reports_an_empty_list(tmp_path: Path) -> None:
    """Boundary: absent and empty must not be the same thing, or a reader cannot tell them apart."""
    path = _write(tmp_path, "m.py", "def f():\n    pass\n")
    assert extract_ast_dict(path)["imports"] == []


def test_the_contract_declares_the_fields_later_sub_features_fill(tmp_path: Path) -> None:
    """Boundary: `AD-1` widens the seam once so SF-03 and SF-04 populate rather than reshape."""
    path = _write(tmp_path, "m.py", "class K:\n    def m(self):\n        pass\n")
    ast = extract_ast_dict(path)
    assert "imports" in ast
    for child in ast["children"]:
        assert child["supertypes"] == []
        assert child["calls"] == []


def test_a_file_that_cannot_be_read_still_has_the_shape(tmp_path: Path) -> None:
    """Graceful degradation: a consumer must never have to guess whether a key exists."""
    ast = extract_ast_dict(str(tmp_path / "absent.py"))
    assert ast["imports"] == []
    assert ast["children"] == []


def test_an_unparseable_file_still_has_the_shape(tmp_path: Path) -> None:
    """Hostile: source the grammar cannot make sense of must not break the contract."""
    path = _write(tmp_path, "m.py", "def (((:\n  ???\n")
    ast = extract_ast_dict(path)
    assert ast["imports"] == []
    assert isinstance(ast["children"], list)
