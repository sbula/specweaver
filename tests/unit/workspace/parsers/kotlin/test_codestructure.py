# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the Kotlin AST Parser."""

from __future__ import annotations

import pytest

from specweaver.workspace.parsers.interfaces import CodeStructureError
from specweaver.workspace.parsers.kotlin.codestructure import KotlinCodeStructure


@pytest.fixture
def parser() -> KotlinCodeStructure:
    return KotlinCodeStructure()


def test_extract_skeleton_strips_bodies(parser: KotlinCodeStructure) -> None:
    code = """
package com.example

class MyKotlinClass {
    init {
        println("Init")
    }

    fun myMethod(a: String): Boolean {
        println("Should be stripped")
        return true
    }
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "package com.example" in skeleton
    assert "class MyKotlinClass {" in skeleton
    assert "init {" in skeleton
    assert "fun myMethod(a: String): Boolean {" in skeleton
    assert "{ ... }" in skeleton
    assert 'println("Init")' not in skeleton
    assert 'println("Should be stripped")' not in skeleton


def test_extract_skeleton_preserves_docstrings(parser: KotlinCodeStructure) -> None:
    code = """
/**
 * This is a kotlin docstring.
 */
fun myFunc() {
    val x = 10
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "fun myFunc() {" in skeleton
    assert "This is a kotlin docstring." in skeleton
    assert "val x = 10" not in skeleton
    assert "{ ... }" in skeleton


def test_extract_skeleton_empty_string(parser: KotlinCodeStructure) -> None:
    assert parser.extract_skeleton("") == ""
    assert parser.extract_skeleton("   ") == "   "


def test_extract_symbol_success(parser: KotlinCodeStructure) -> None:
    code = """
class TargetClass {
    val value: Boolean = true

    fun do_thing() {
        println("success")
    }
}

object TargetObject {
    fun process() {}
}

fun standaloneFunc() = 5
"""

    target_cls = parser.extract_symbol(code, "TargetClass")
    assert "class TargetClass {" in target_cls
    assert "val value: Boolean = true" in target_cls
    assert "fun do_thing() {" in target_cls
    assert "TargetObject" not in target_cls

    target_obj = parser.extract_symbol(code, "TargetObject")
    assert "object TargetObject {" in target_obj
    assert "fun process() {}" in target_obj

    target_func = parser.extract_symbol(code, "standaloneFunc")
    assert "fun standaloneFunc() = 5" in target_func


def test_extract_symbol_not_found(parser: KotlinCodeStructure) -> None:
    code = "class existing {}"

    with pytest.raises(CodeStructureError, match=r"Symbol \'Missing\' not found in the AST\."):
        parser.extract_symbol(code, "Missing")


def test_extract_symbol_empty_string(parser: KotlinCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match=r"Cannot extract \'Anything\' from empty code\."):
        parser.extract_symbol("", "Anything")


def test_extract_symbol_annotation_preservation(parser: KotlinCodeStructure) -> None:
    code = """
    class TargetClass {
        @Override
        fun method() {
            return
        }
    }
    """
    target_fn = parser.extract_symbol(code, "TargetClass.method")
    assert "@Override" in target_fn
    assert "fun method() {" in target_fn


def test_extract_symbol_malformed_syntax(parser: KotlinCodeStructure) -> None:
    code = """fun broken(::: {{}

fun good(): Boolean { return true }"""
    try:
        target = parser.extract_symbol(code, "good")
        assert "fun good" in target
    except CodeStructureError:
        pass


def test_list_and_extract_dot_notation(parser: KotlinCodeStructure) -> None:
    code = """
    class Database {
        fun connect() {
            return
        }

        class Inner {
            fun query() {
            }
        }
    }
    """
    symbols = parser.list_symbols(code)
    assert "Database" in symbols
    assert "Database.connect" in symbols
    assert "Database.Inner" in symbols
    assert "Inner.query" in symbols

    target = parser.extract_symbol(code, "Database.connect")
    assert "fun connect()" in target
    assert "class Database" not in target


def test_extract_framework_markers_success(parser: KotlinCodeStructure) -> None:
    code = """
@RestController
@RequestMapping("/api")
class MyController : BaseController(), InterfaceA, InterfaceB {
    @get:GetMapping("/")
    @Transactional
    fun myMethod() { }
}
"""
    markers = parser.extract_framework_markers(code)

    assert "MyController" in markers
    assert "RestController" in markers["MyController"]["decorators"]
    assert 'RequestMapping("/api")' in markers["MyController"]["decorators"]
    assert "BaseController" in markers["MyController"]["extends"]
    assert "InterfaceA" in markers["MyController"]["extends"]
    assert "InterfaceB" in markers["MyController"]["extends"]

    assert "MyController.myMethod" in markers
    assert "Transactional" in markers["MyController.myMethod"]["decorators"]
    assert "extends" not in markers["MyController.myMethod"]


def test_extract_framework_markers_empty(parser: KotlinCodeStructure) -> None:
    code = "class Simple {}"
    markers = parser.extract_framework_markers(code)
    assert markers == {"Simple": {"decorators": [], "extends": []}}


def test_list_symbols_decorator_filter(parser: KotlinCodeStructure) -> None:
    code = """
@RestController
class MyController {
    fun myMethod() { }
}

class OtherController {
    fun otherMethod() { }
}
"""
    symbols = parser.list_symbols(code, decorator_filter="RestController")
    assert "MyController" in symbols
    assert "OtherController" not in symbols
