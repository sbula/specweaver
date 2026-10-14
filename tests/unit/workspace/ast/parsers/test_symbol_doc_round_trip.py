# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The comment above a symbol, written, read back, replaced and removed: nothing else changes.

Proves: D-SENS-06 FR-14

| Bucket | Case |
|---|---|
| Happy | a new doc in each of 8 languages, in its usual style; read back without markers |
| Boundary | a method inside a class; a Python docstring as the only statement; a one-line doc |
| Degradation | an existing doc keeps its own marker style; a neighbour's doc stays |
| Hostile | a missing symbol; a doc that would close its own comment; SQL and Markdown |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.cpp.codestructure import CppCodeStructure
from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

_DOC = "Adds up.\n\nTwo lines."

# (parser, code without a doc, symbol, the same code with _DOC written)
_CASES = {
    "python": (
        PythonCodeStructure(),
        "import os\n\n\ndef total(a):\n    return a\n",
        "total",
        'import os\n\n\ndef total(a):\n    """Adds up.\n\n    Two lines.\n    """\n    return a\n',
    ),
    "java": (
        JavaCodeStructure(),
        "class Calc {\n    int total(int a) {\n        return a;\n    }\n}\n",
        "Calc.total",
        "class Calc {\n    /**\n     * Adds up.\n     *\n     * Two lines.\n     */\n"
        "    int total(int a) {\n        return a;\n    }\n}\n",
    ),
    "kotlin": (
        KotlinCodeStructure(),
        "fun total(a: Int): Int {\n    return a\n}\n",
        "total",
        "/**\n * Adds up.\n *\n * Two lines.\n */\nfun total(a: Int): Int {\n    return a\n}\n",
    ),
    "typescript": (
        TypeScriptCodeStructure(),
        "export function total(a: number): number {\n    return a;\n}\n",
        "total",
        "/**\n * Adds up.\n *\n * Two lines.\n */\n"
        "export function total(a: number): number {\n    return a;\n}\n",
    ),
    "rust": (
        RustCodeStructure(),
        "pub fn total(a: u32) -> u32 {\n    a\n}\n",
        "total",
        "/// Adds up.\n///\n/// Two lines.\npub fn total(a: u32) -> u32 {\n    a\n}\n",
    ),
    "go": (
        GoCodeStructure(),
        "package m\n\nfunc Total(a int) int {\n\treturn a\n}\n",
        "Total",
        "package m\n\n// Adds up.\n//\n// Two lines.\nfunc Total(a int) int {\n\treturn a\n}\n",
    ),
    "c": (
        CCodeStructure(),
        "int total(int a) {\n    return a;\n}\n",
        "total",
        "/**\n * Adds up.\n *\n * Two lines.\n */\nint total(int a) {\n    return a;\n}\n",
    ),
    "cpp": (
        CppCodeStructure(),
        "int total(int a) {\n    return a;\n}\n",
        "total",
        "/**\n * Adds up.\n *\n * Two lines.\n */\nint total(int a) {\n    return a;\n}\n",
    ),
}


@pytest.mark.parametrize("language", sorted(_CASES))
def test_a_new_doc_is_written_in_the_usual_style(language: str) -> None:
    parser, code, symbol, documented = _CASES[language]
    assert parser.replace_symbol_doc(code, symbol, _DOC) == documented


@pytest.mark.parametrize("language", sorted(_CASES))
def test_the_doc_reads_back_without_its_markers(language: str) -> None:
    parser, code, symbol, _ = _CASES[language]
    written = parser.replace_symbol_doc(code, symbol, _DOC)
    assert parser.extract_symbol_doc(written, symbol) == _DOC


@pytest.mark.parametrize("language", sorted(_CASES))
def test_a_replaced_doc_changes_only_the_doc(language: str) -> None:
    parser, code, symbol, documented = _CASES[language]
    replaced = parser.replace_symbol_doc(documented, symbol, "Sums.")
    assert parser.extract_symbol_doc(replaced, symbol) == "Sums."
    assert parser.replace_symbol_doc(replaced, symbol, "") == code


@pytest.mark.parametrize("language", sorted(_CASES))
def test_an_empty_doc_removes_it(language: str) -> None:
    parser, code, symbol, documented = _CASES[language]
    assert parser.replace_symbol_doc(documented, symbol, "") == code
    assert parser.replace_symbol_doc(code, symbol, "") == code


@pytest.mark.parametrize(
    ("parser", "code", "symbol", "expected"),
    [
        (
            GoCodeStructure(),
            "package m\n\n/* Old. */\nfunc F() {}\n",
            "F",
            "package m\n\n/*\n * New.\n */\nfunc F() {}\n",
        ),
        (
            CCodeStructure(),
            "// Old.\n// More.\nint f(void) { return 0; }\n",
            "f",
            "// New.\nint f(void) { return 0; }\n",
        ),
        (
            RustCodeStructure(),
            "/** Old. */\nfn f() {}\n",
            "f",
            "/**\n * New.\n */\nfn f() {}\n",
        ),
    ],
)
def test_an_existing_doc_keeps_its_own_style(parser, code, symbol, expected) -> None:  # type: ignore[no-untyped-def]
    assert parser.replace_symbol_doc(code, symbol, "New.") == expected


def test_a_neighbours_doc_and_a_detached_comment_stay() -> None:
    code = (
        "// licence\n\n// First.\nint first(void) { return 1; }\n\n"
        "// Second.\nint second(void) { return 2; }\n"
    )
    replaced = CCodeStructure().replace_symbol_doc(code, "second", "Other.")
    assert replaced == code.replace("// Second.", "// Other.")
    assert CCodeStructure().replace_symbol_doc(code, "first", "") == code.replace("// First.\n", "")


def test_a_one_line_python_doc_and_a_class_method() -> None:
    code = "class A:\n    def f(self):\n        return 1\n"
    assert PythonCodeStructure().replace_symbol_doc(code, "A.f", "Once.") == (
        'class A:\n    def f(self):\n        """Once."""\n        return 1\n'
    )


def test_removing_the_only_statement_of_a_python_body_leaves_pass() -> None:
    code = 'def f():\n    """Only this."""\n'
    assert PythonCodeStructure().replace_symbol_doc(code, "f", "") == "def f():\n    pass\n"


@pytest.mark.parametrize(
    ("parser", "code", "symbol", "doc"),
    [
        (PythonCodeStructure(), "def f():\n    return 1\n", "missing", "x"),
        (PythonCodeStructure(), "def f():\n    return 1\n", "f", 'say """ no'),
        (PythonCodeStructure(), "def f(): return 1\n", "f", "x"),
        (JavaCodeStructure(), "class A {}\n", "A", "ends */ here"),
        (CCodeStructure(), "int x; int f(void) { return 0; }\n", "f", "x"),
        (CCodeStructure(), "int x; // note\nint f(void) { return 0; }\n", "f", "x"),
        (SqlCodeStructure(), "CREATE TABLE t (id INT);\n", "t", "x"),
        (MarkdownCodeStructure(), "# Title\n\ntext\n", "Title", "x"),
    ],
)
def test_a_doc_that_cannot_be_written_refuses(parser, code, symbol, doc) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(CodeStructureError):
        parser.replace_symbol_doc(code, symbol, doc)


def test_only_code_languages_offer_the_doc_intents() -> None:
    for parser, *_ in _CASES.values():
        assert {"doc", "replace_doc"} <= set(parser.supported_intents())
    for parser in (SqlCodeStructure(), MarkdownCodeStructure()):
        assert not {"doc", "replace_doc"} & set(parser.supported_intents())


# --- a doc above an attribute, a decorator or a template ------------------------------------


@pytest.mark.parametrize(
    ("parser", "code", "symbol", "expected"),
    [
        (
            RustCodeStructure(),
            "/// Old.\n#[derive(Debug)]\npub struct S {}\n",
            "S",
            "/// New.\n#[derive(Debug)]\npub struct S {}\n",
        ),
        (
            RustCodeStructure(),
            "#[test]\n#[ignore]\nfn f() {}\n",
            "f",
            "/// New.\n#[test]\n#[ignore]\nfn f() {}\n",
        ),
        (
            CppCodeStructure(),
            "/** Old. */\ntemplate <typename T>\nT f(T a) { return a; }\n",
            "f",
            "/**\n * New.\n */\ntemplate <typename T>\nT f(T a) { return a; }\n",
        ),
        (
            CppCodeStructure(),
            "template <typename T>\nclass Box {};\n",
            "Box",
            "/**\n * New.\n */\ntemplate <typename T>\nclass Box {};\n",
        ),
        (
            TypeScriptCodeStructure(),
            "/** Old. */\n@Component({})\nexport class A {}\n",
            "A",
            "/**\n * New.\n */\n@Component({})\nexport class A {}\n",
        ),
        (
            TypeScriptCodeStructure(),
            "class A {\n    @Input()\n    m(): void {}\n}\n",
            "A.m",
            "class A {\n    /**\n     * New.\n     */\n    @Input()\n    m(): void {}\n}\n",
        ),
    ],
)
def test_the_doc_sits_above_attributes_decorators_and_templates(  # type: ignore[no-untyped-def]
    parser, code, symbol, expected
) -> None:
    assert parser.replace_symbol_doc(code, symbol, "New.") == expected
    assert parser.extract_symbol_doc(expected, symbol) == "New."


def test_an_attribute_after_a_blank_line_keeps_the_doc_detached() -> None:
    code = "/// Licence.\n\n#[test]\nfn f() {}\n"
    assert RustCodeStructure().extract_symbol_doc(code, "f") == ""


# --- line endings ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("parser", "code", "symbol", "expected"),
    [
        (
            GoCodeStructure(),
            "package m\r\n\r\nfunc F() {}\r\n",
            "F",
            "package m\r\n\r\n// A.\r\n// B.\r\nfunc F() {}\r\n",
        ),
        (
            JavaCodeStructure(),
            "class A {}\r\n",
            "A",
            "/**\r\n * A.\r\n * B.\r\n */\r\nclass A {}\r\n",
        ),
        (
            PythonCodeStructure(),
            "def f():\r\n    return 1\r\n",
            "f",
            'def f():\r\n    """A.\r\n    B.\r\n    """\r\n    return 1\r\n',
        ),
    ],
)
def test_a_crlf_file_gets_crlf_doc_lines(parser, code, symbol, expected) -> None:  # type: ignore[no-untyped-def]
    assert parser.replace_symbol_doc(code, symbol, "A.\nB.") == expected
    assert parser.extract_symbol_doc(expected, symbol) == "A.\nB."
    assert parser.replace_symbol_doc(expected, symbol, "") == code
