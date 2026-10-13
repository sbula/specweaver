# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every symbol a parser lists can be read back by that name, in every language D-SENS-03 adds.

Proves: D-SENS-03 FR-1
Proves: D-SENS-03 FR-2
Proves: D-SENS-03 FR-3
Proves: D-SENS-03 FR-4
Proves: D-SENS-03 FR-5

| Bucket | Case |
|---|---|
| Happy | C, C++, Go, SQL and Markdown: each listed symbol reads back |
| Boundary | a Markdown heading with a dot in it (`## 2. Scope`), as SpecWeaver's own specs are numbered |
| Degradation | not applicable — the input parses |
| Hostile | not applicable — the input is the user's own code |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.cpp.codestructure import CppCodeStructure
from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure
from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure

_SOURCES = {
    "c": (
        CCodeStructure,
        "int add(int a, int b) {\n    return a + b;\n}\n\nstatic int hidden(void) { return 0; }\n",
    ),
    "cpp": (
        CppCodeStructure,
        "class Shape {\npublic:\n    double area(double r) { return r; }\n};\n",
    ),
    "go": (GoCodeStructure, 'package srv\n\nfunc Hello() string {\n\treturn "hi"\n}\n'),
    "sql": (
        SqlCodeStructure,
        "CREATE TABLE users (\n    id INT\n);\n\nCREATE VIEW active AS SELECT id FROM users;\n",
    ),
    "md": (
        MarkdownCodeStructure,
        "# Spec\n\nIntro.\n\n## 1. Purpose\n\nWhy.\n\n## 2. Scope\n\nWhat.\n\n### 2.1 Out\n\nNot this.\n",
    ),
}


@pytest.mark.parametrize("language", sorted(_SOURCES))
def test_every_listed_symbol_reads_back(language: str) -> None:
    parser_cls, code = _SOURCES[language]
    parser = parser_cls()
    symbols = parser.list_symbols(code)

    assert symbols, language
    for name in symbols:
        assert parser.extract_symbol(code, name), (language, name)


def test_a_numbered_markdown_section_is_read_whole() -> None:
    parser = MarkdownCodeStructure()

    section = parser.extract_symbol(_SOURCES["md"][1], "Spec.2. Scope")

    assert section.startswith("## 2. Scope") and "Not this." in section and "Why." not in section


def test_every_registered_parser_shares_the_base() -> None:
    from specweaver.workspace.ast.parsers.base import BaseTreeSitterParser
    from specweaver.workspace.ast.parsers.factory import get_default_parsers

    assert all(isinstance(p, BaseTreeSitterParser) for p in get_default_parsers().values())
