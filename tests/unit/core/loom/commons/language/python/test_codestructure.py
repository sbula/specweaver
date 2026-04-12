# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the Python AST Parser."""

from __future__ import annotations

import pytest

from specweaver.core.loom.commons.language.interfaces import CodeStructureError
from specweaver.core.loom.commons.language.python.codestructure import PythonCodeStructure


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
