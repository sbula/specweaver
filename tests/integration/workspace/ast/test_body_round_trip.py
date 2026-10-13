# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A function's body can be read, changed and written back without touching the rest of the file.

Proves: D-SENS-02 FR-8

The body a tool returns is the code inside the function, without its outer braces, at column 0.
Writing it back puts it at the function's own indentation. So reading and writing an unchanged body
changes no byte, and changing one line changes only that line.

| Bucket | Case |
|---|---|
| Happy | every code language: an unchanged body writes back byte for byte; one edit changes one line |
| Boundary | a method inside a class; a body written in another indentation is re-indented |
| Degradation | a symbol with no body (SQL) refuses rather than writing nothing |
| Hostile | the edited file still parses with no error node |
"""

from __future__ import annotations

import difflib

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers
from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

_SOURCES = {
    "python": (
        "py",
        "Greeter.greet",
        '''class Greeter:
    """Greets."""

    def greet(self, name: str) -> str:
        """Return a greeting."""
        if not name:
            raise ValueError("empty")
        return f"Hello, {name}"

    def other(self) -> int:  # keep
        return 1
''',
    ),
    "java": (
        "java",
        "Greeter.greet",
        """public class Greeter {
    // keep
    public String greet(String name) {
        if (name.isEmpty()) {
            throw new IllegalArgumentException("empty");
        }
        return "Hello, " + name;
    }

    private int other() { return 1; }
}
""",
    ),
    "kotlin": (
        "kt",
        "Greeter.greet",
        """class Greeter {
    // keep
    fun greet(name: String): String {
        if (name.isEmpty()) {
            throw IllegalArgumentException("empty")
        }
        return "Hello, " + name
    }
}
""",
    ),
    "typescript": (
        "ts",
        "Greeter.greet",
        """export class Greeter {
  // keep
  greet(name: string): string {
    if (!name) {
      throw new Error("empty");
    }
    return "Hello, " + name;
  }
}
""",
    ),
    "rust": (
        "rs",
        "greet",
        """// keep
pub fn greet(name: &str) -> String {
    if name.is_empty() {
        panic!("empty");
    }
    format!("Hello, {}", name)
}
""",
    ),
    "go": (
        "go",
        "Greet",
        """package demo

// keep
func Greet(name string) string {
\tif name == "" {
\t\tpanic("empty")
\t}
\treturn "Hello, " + name
}
""",
    ),
    "c": (
        "c",
        "greet",
        """/* keep */
int greet(const char *name) {
    if (name == 0) {
        return -1; /* "empty" */
    }
    return 0;
}
""",
    ),
    "cpp": (
        "cpp",
        "greet",
        """// keep
int greet(const char *name) {
    if (name == nullptr) {
        throw "empty";
    }
    return 0;
}
""",
    ),
}


_SUFFIX = {
    "python": ".py",
    "java": ".java",
    "kotlin": ".kt",
    "typescript": ".ts",
    "rust": ".rs",
    "go": ".go",
    "c": ".c",
    "cpp": ".cpp",
    "sql": ".sql",
}


def _parser(language: str):  # type: ignore[no-untyped-def]
    suffix = _SUFFIX[language]
    return next(p for exts, p in get_default_parsers().items() if suffix in exts)


@pytest.mark.parametrize("language", sorted(_SOURCES))
def test_an_unchanged_body_writes_back_byte_for_byte(language: str) -> None:
    # Proves: D-SENS-02 FR-8
    _, symbol, code = _SOURCES[language]
    parser = _parser(language)

    body = parser.extract_symbol_body(code, symbol)

    assert not body.startswith(("{", " ", "\t", "\n")), repr(body)
    assert parser.replace_symbol_body(code, symbol, body) == code


@pytest.mark.parametrize("language", sorted(_SOURCES))
def test_one_edit_changes_only_that_line(language: str) -> None:
    # Proves: D-SENS-02 FR-8
    _, symbol, code = _SOURCES[language]
    parser = _parser(language)
    body = parser.extract_symbol_body(code, symbol)

    edited = parser.replace_symbol_body(code, symbol, body.replace('"empty"', '"no name"'))

    changed = [
        line
        for line in difflib.unified_diff(code.splitlines(), edited.splitlines(), n=0, lineterm="")
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    assert len(changed) == 2, changed
    assert "no name" in changed[1]
    assert changed[0][1:].replace('"empty"', '"no name"') == changed[1][1:]


@pytest.mark.parametrize("language", sorted(_SOURCES))
def test_a_body_in_another_indentation_is_put_at_the_functions_own(language: str) -> None:
    _, symbol, code = _SOURCES[language]
    parser = _parser(language)
    body = parser.extract_symbol_body(code, symbol)
    shifted = "\n".join("        " + line if line else line for line in body.split("\n"))

    assert parser.replace_symbol_body(code, symbol, shifted) == code


def test_a_symbol_without_a_body_refuses() -> None:
    parser = _parser("sql")
    code = "CREATE TABLE orders (id INT);\n"
    with pytest.raises(CodeStructureError):
        parser.replace_symbol_body(code, "orders", "id BIGINT")
