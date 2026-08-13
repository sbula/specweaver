# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The framework-marker walk four class-based parsers shared, and the query that varies.

`TECH-037`. `extract_framework_markers` was written out four times — `java`, `python` and
`typescript` character-for-character identical, `kotlin` differing by a single blank line. The only
genuinely per-language part is the tree-sitter query naming that language's class and function
declarations, which is the same shape as the `SCM_*` properties already on the base.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

#: The class-based parsers that take the shared walk.
SHARED = [JavaCodeStructure, KotlinCodeStructure, PythonCodeStructure, TypeScriptCodeStructure]

#: One decorated class and one decorated function per language, so the walk has both shapes.
SOURCES = {
    "JavaCodeStructure": (
        "@Service\npublic class Greeter {\n  @Inject\n  public void greet() {}\n}\n",
        "Greeter",
    ),
    "KotlinCodeStructure": (
        "@Service\nclass Greeter {\n  @Inject\n  fun greet() {}\n}\n",
        "Greeter",
    ),
    "PythonCodeStructure": (
        "@service\nclass Greeter:\n    @inject\n    def greet(self):\n        pass\n",
        "Greeter",
    ),
    "TypeScriptCodeStructure": (
        "@Service\nclass Greeter {\n  @Inject\n  greet() {}\n}\n",
        "Greeter",
    ),
}


@pytest.mark.parametrize("parser_cls", SHARED, ids=lambda c: c.__name__)
class TestExtractFrameworkMarkers:
    def test_empty_source_yields_no_markers(self, parser_cls: type) -> None:
        assert parser_cls().extract_framework_markers("   \n") == {}

    def test_the_declared_class_is_reported(self, parser_cls: type) -> None:
        source, class_name = SOURCES[parser_cls.__name__]

        markers = parser_cls().extract_framework_markers(source)

        assert class_name in markers, f"{parser_cls.__name__} found {sorted(markers)}"

    def test_a_class_entry_carries_its_bases(self, parser_cls: type) -> None:
        """`extends` is present for a class and absent for a function — the `is_class` branch."""
        source, class_name = SOURCES[parser_cls.__name__]

        entry = parser_cls().extract_framework_markers(source)[class_name]

        assert "extends" in entry
        assert "decorators" in entry

    def test_the_walk_is_not_redeclared_on_the_language(self, parser_cls: type) -> None:
        """Four copies became one; a regression would silently restore a per-language walk."""
        assert "extract_framework_markers" not in vars(parser_cls), (
            f"{parser_cls.__name__} re-declares the shared marker walk"
        )

    def test_the_language_declares_only_its_query(self, parser_cls: type) -> None:
        """The variance must be stated as data, not reimplemented as control flow."""
        assert "SCM_FRAMEWORK_QUERY" in vars(parser_cls)
