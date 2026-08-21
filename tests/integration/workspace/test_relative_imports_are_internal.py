# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A module whose imports are all relative is not an adapter.

Proves: TECH-068 FR-5

`infer_archetype` calls `extract_imports` and asks whether the root of each import is external. A
relative import is internal by definition — the dots say so — yet it reached that check as a bare
symbol name and was judged external, so any package using relative imports inferred `adapter`.

Fixing the parser alone moves the defect rather than closing it: `".sibling".split(".")[0]` is the
empty string, which is equally absent from the stdlib list and equally not `specweaver`. The seam is
the claim, which is why this test lives one layer out from the parser's own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workspace.analyzers.factory import PythonAnalyzer

if TYPE_CHECKING:
    from pathlib import Path


def test_a_package_of_relative_imports_is_pure_logic(tmp_path: Path) -> None:
    """Happy path: the archetype heuristic sees an internal dependency, not a foreign one."""
    (tmp_path / "sibling.py").write_text("VALUE = 1\n")
    (tmp_path / "mod.py").write_text("from .sibling import VALUE\n")
    assert PythonAnalyzer().infer_archetype(tmp_path) == "pure-logic"


def test_a_parent_relative_import_is_also_internal(tmp_path: Path) -> None:
    """Boundary: more dots is still internal."""
    (tmp_path / "mod.py").write_text("from ..pkg.mod import Thing\n")
    assert PythonAnalyzer().infer_archetype(tmp_path) == "pure-logic"


def test_a_genuine_external_import_still_reads_as_adapter(tmp_path: Path) -> None:
    """Boundary: the correct half must stay correct, or the fix is just a weaker check."""
    (tmp_path / "mod.py").write_text("import httpx\n")
    assert PythonAnalyzer().infer_archetype(tmp_path) == "adapter"


def test_a_stdlib_import_is_not_an_adapter(tmp_path: Path) -> None:
    """Graceful degradation: the stdlib list still governs."""
    (tmp_path / "mod.py").write_text("import os\n")
    assert PythonAnalyzer().infer_archetype(tmp_path) == "pure-logic"
