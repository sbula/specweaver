# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the Python AST Parser."""

from __future__ import annotations

import pytest

from specweaver.workspace.parsers.interfaces import CodeStructureError
from specweaver.workspace.parsers.python.codestructure import PythonCodeStructure


@pytest.fixture
def parser() -> PythonCodeStructure:
    return PythonCodeStructure()


def test_extract_skeleton_strips_bodies(parser: PythonCodeStructure) -> None:
    code = """
import os

def my_func(a: int) -> str:
    print("Should be stripped")
    return "X"

class MyClass:
    def method(self):
        y = 2
        return y
"""
    skeleton = parser.extract_skeleton(code)

    assert "import os" in skeleton
    assert "def my_func(a: int) -> str:" in skeleton
    assert "class MyClass:" in skeleton
    assert "def method(self):" in skeleton
    assert "..." in skeleton
    assert "Should be stripped" not in skeleton
    assert "y = 2" not in skeleton


def test_extract_skeleton_preserves_docstrings(parser: PythonCodeStructure) -> None:
    code = '''
def my_func():
    """This is a docstring."""
    x = 10
    return x
'''
    skeleton = parser.extract_skeleton(code)

    assert "def my_func():" in skeleton
    assert '"""This is a docstring."""' in skeleton
    assert "x = 10" not in skeleton
    assert "..." in skeleton


def test_extract_skeleton_empty_string(parser: PythonCodeStructure) -> None:
    assert parser.extract_skeleton("") == ""
    assert parser.extract_skeleton("   ") == "   "


def test_extract_symbol_success(parser: PythonCodeStructure) -> None:
    code = """
def func1():
    print("1")

class TargetClass:
    def method(self):
        return True

def TargetFunc():
    return "success"
"""

    target_cls = parser.extract_symbol(code, "TargetClass")
    assert "class TargetClass:" in target_cls
    assert "def method(self):" in target_cls
    assert "return True" in target_cls
    assert "func1" not in target_cls

    target_fn = parser.extract_symbol(code, "TargetFunc")
    assert "def TargetFunc():" in target_fn
    assert 'return "success"' in target_fn
    assert "TargetClass" not in target_fn


def test_extract_symbol_not_found(parser: PythonCodeStructure) -> None:
    code = "def existing(): pass"

    with pytest.raises(CodeStructureError, match=r"Symbol \'Missing\' not found in the AST\."):
        parser.extract_symbol(code, "Missing")


def test_extract_symbol_empty_string(parser: PythonCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match=r"Cannot extract \'Anything\' from empty code\."):
        parser.extract_symbol("", "Anything")


def test_extract_symbol_malformed_syntax(parser: PythonCodeStructure) -> None:
    code = """def existing(: pass

def Good(): return True"""
    try:
        target = parser.extract_symbol(code, "Good")
        assert "def Good():" in target
    except CodeStructureError:
        pass


def test_extract_symbol_scope_collision(parser: PythonCodeStructure) -> None:
    code = """
class Parent:
    def collide(self): return 1
def collide(): return 2
"""
    # We expect no crashes, should grab one of them predictably
    target = parser.extract_symbol(code, "collide")
    assert "collide" in target


def test_extract_symbol_decorator_preservation(parser: PythonCodeStructure) -> None:
    code = """
@app.route('/test')
@classmethod
def DecoratedFunc():
    return True
"""
    target = parser.extract_symbol(code, "DecoratedFunc")
    assert "@app.route" in target
    assert "@classmethod" in target
    assert "def DecoratedFunc():" in target


def test_extract_symbol_async_support(parser: PythonCodeStructure) -> None:
    code = """
async def AsyncFunc():
    return await True
"""
    target = parser.extract_symbol(code, "AsyncFunc")
    assert "async def AsyncFunc():" in target


def test_extract_framework_markers_success(parser: PythonCodeStructure) -> None:
    code = """
@pytest.mark.asyncio
@app.route('/api')
class MyController(BaseController, WebMixin):
    @property
    def get_data(self):
        pass
"""
    markers = parser.extract_framework_markers(code)

    assert "MyController" in markers
    assert markers["MyController"]["decorators"] == ["pytest.mark.asyncio", "app.route('/api')"]
    assert markers["MyController"]["extends"] == ["BaseController", "WebMixin"]

    assert "get_data" in markers
    assert markers["get_data"]["decorators"] == ["property"]
    assert "extends" not in markers["get_data"]


def test_extract_framework_markers_empty(parser: PythonCodeStructure) -> None:
    code = "def simple(): pass"
    markers = parser.extract_framework_markers(code)
    assert markers == {"simple": {"decorators": []}}


def test_list_symbols_decorator_filter(parser: PythonCodeStructure) -> None:
    code = """
@app.route('/api')
class MyController:
    pass

class OtherController:
    pass
"""
    symbols = parser.list_symbols(code, decorator_filter="app.route")
    assert "MyController" in symbols
    assert "OtherController" not in symbols

# ---------------------------------------------------------------------------
# Edge Case Edge Branch Testing
# ---------------------------------------------------------------------------


def test_extract_imports_from_statement(parser: PythonCodeStructure) -> None:
    code = "from specweaver.core import flow\nfrom os import path"
    imports = parser.extract_imports(code)
    assert "specweaver.core" in imports
    assert "os" in imports

def test_extract_imports_direct_statement(parser: PythonCodeStructure) -> None:
    code = "import json\nimport sys"
    imports = parser.extract_imports(code)
    assert "json" in imports
    assert "sys" in imports

def test_extract_imports_empty(parser: PythonCodeStructure) -> None:
    assert parser.extract_imports("") == []
    assert parser.extract_imports("   ") == []

def test_list_symbols_empty(parser: PythonCodeStructure) -> None:
    assert parser.list_symbols("") == []
    assert parser.list_symbols("   ") == []

def test_auto_indent_empty(parser: PythonCodeStructure) -> None:
    assert parser._auto_indent("", 4) == ""

def test_replace_symbol_empty(parser: PythonCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match="Cannot replace 'foo' in empty code"):
        parser.replace_symbol("", "foo", "bar")

def test_replace_symbol_not_found(parser: PythonCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match="Symbol 'Missing' not found"):
        parser.replace_symbol("def foo(): pass", "Missing", "bar")

def test_replace_symbol_success(parser: PythonCodeStructure) -> None:
    code = "def old():\n    pass\n"
    new_code = "def new():\n    return 42"
    result = parser.replace_symbol(code, "old", new_code)
    assert "new()" in result
    assert "old()" not in result

def test_extract_symbol_finds_decorated_node(parser: PythonCodeStructure) -> None:
    code = "@pytest.mark.asyncio\nasync def TestFunc():\n    pass\n"
    node = parser._find_symbol_node(parser.parser.parse(code.encode('utf-8')), "TestFunc")
    assert node is not None
    assert node.type == "decorated_definition"

