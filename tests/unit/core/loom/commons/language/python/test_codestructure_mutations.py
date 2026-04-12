# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import pytest

from specweaver.core.loom.commons.language.interfaces import CodeStructureError
from specweaver.core.loom.commons.language.python.codestructure import PythonCodeStructure


@pytest.fixture
def parser() -> PythonCodeStructure:
    return PythonCodeStructure()


def test_auto_indent_no_code(parser: PythonCodeStructure) -> None:
    assert parser._auto_indent("", 4) == ""


def test_auto_indent_multiline_preserves_first_line(parser: PythonCodeStructure) -> None:
    code = "def inner():\npass"
    res = parser._auto_indent(code, 4)
    assert res == "def inner():\n    pass"


def test_replace_symbol_exact_indentation(parser: PythonCodeStructure) -> None:
    code = "class Top:\n    def original(self):\n        return 1\n"
    new_code = "def new_method(self):\n    return 2"
    mutated = parser.replace_symbol(code, "original", new_code)

    assert "def new_method(self):" in mutated
    assert "        return 2" in mutated
    assert "def original(self):" not in mutated


def test_replace_symbol_body_indents_nested(parser: PythonCodeStructure) -> None:
    code = "class A:\n    def target(self):\n        pass\n"
    new_code = "print(1)\nprint(2)"
    mutated = parser.replace_symbol_body(code, "target", new_code)

    assert "def target(self):" in mutated
    assert "        print(1)\n        print(2)" in mutated
    assert "pass" not in mutated


def test_replace_symbol_body_empty_code_throws(parser: PythonCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match="Cannot replace body of 'test' in empty code"):
        parser.replace_symbol_body("   ", "test", "pass")


def test_delete_symbol_removes_entire_block(parser: PythonCodeStructure) -> None:
    code = "def a(): pass\n\ndef b(): pass\n"
    mutated = parser.delete_symbol(code, "a")
    assert "def a(): pass" not in mutated
    assert "def b(): pass" in mutated


def test_delete_symbol_missing_target(parser: PythonCodeStructure) -> None:
    code = "def a(): pass"
    with pytest.raises(CodeStructureError, match="Symbol 'missing' not found"):
        parser.delete_symbol(code, "missing")


def test_delete_symbol_empty_code_returns_empty(parser: PythonCodeStructure) -> None:
    assert parser.delete_symbol("   ", "anything") == "   "


def test_add_symbol_eof_fallback(parser: PythonCodeStructure) -> None:
    code = "def start(): pass\n"
    new_code = "def global_added():\n    pass"
    mutated = parser.add_symbol(code, None, new_code)

    # Needs to be unindented since it's global EOF
    assert "def global_added():\n    pass" in mutated
    # Ensure double newline fallback handles properly
    assert "\n\ndef global_added" in mutated


def test_add_symbol_eof_no_newline(parser: PythonCodeStructure) -> None:
    code = "def start(): pass"
    new_code = "def added(): pass"
    mutated = parser.add_symbol(code, None, new_code)
    assert mutated == "def start(): pass\n\ndef added(): pass"


def test_add_symbol_nested_target(parser: PythonCodeStructure) -> None:
    code = "class Parent:\n    def a(self): pass\n"
    new_code = "def b(self):\n    pass"
    mutated = parser.add_symbol(code, "Parent", new_code)

    # Should be indented 4 spaces since Parent has 0 margin
    assert "    def b(self):\n        pass" in mutated
    # Should still contain Parent and a
    assert "class Parent:" in mutated
    assert "def a(self):" in mutated
