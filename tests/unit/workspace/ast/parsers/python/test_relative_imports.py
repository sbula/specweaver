# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A relative import names a module, and that is what `extract_imports` must report.

Proves: TECH-068 FR-5

Measured 2026-08-21: `from .sibling import X` reported `['X']` and `from ..pkg.mod import Y`
reported `['Y']` — the imported SYMBOL, not the module. The grammar wraps a relative module in a
`relative_import` node, and the extraction looked only at the direct `dotted_name` children of
`import_from_statement`, so the first one it found was the imported name.

This repository's own `src/` holds 27 relative imports, `sandbox/execution/executor.py` among them,
so it is a live defect rather than a hypothetical one. `TECH-068` FR-5 and FR-8 rest on it: an
import that reports a symbol resolves to no file, so a real dependency reads as an unknown one.

Both spellings of the same dependency must give the same answer. `from . import sibling` and
`from .sibling import X` are each a dependency on `.sibling`.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure


@pytest.fixture
def parser() -> PythonCodeStructure:
    return PythonCodeStructure()


class TestExtractImports:
    def test_a_relative_import_reports_its_module(self, parser: PythonCodeStructure) -> None:
        assert parser.extract_imports("from .sibling import X") == [".sibling"]

    def test_a_parent_relative_import_keeps_every_dot(self, parser: PythonCodeStructure) -> None:
        assert parser.extract_imports("from ..pkg.mod import Y") == ["..pkg.mod"]

    def test_both_spellings_of_one_dependency_agree(self, parser: PythonCodeStructure) -> None:
        """Boundary: `from . import x` names the submodule through the imported name."""
        assert parser.extract_imports("from . import sibling") == [".sibling"]

    def test_a_bare_relative_import_of_several_names(self, parser: PythonCodeStructure) -> None:
        """Boundary: each imported name is a submodule of the same package."""
        assert parser.extract_imports("from . import a, b") == [".a", ".b"]

    def test_an_absolute_import_is_unchanged(self, parser: PythonCodeStructure) -> None:
        """Boundary: the correct half must stay correct."""
        assert parser.extract_imports("import os\nfrom a.b import C\n") == ["a.b", "os"]

    def test_empty_source_reports_nothing(self, parser: PythonCodeStructure) -> None:
        """Graceful degradation."""
        assert parser.extract_imports("") == []

    def test_a_star_import_reports_the_package(self, parser: PythonCodeStructure) -> None:
        """Hostile: a wildcard names no symbol, so only the package is a dependency."""
        assert parser.extract_imports("from .pkg import *") == [".pkg"]
