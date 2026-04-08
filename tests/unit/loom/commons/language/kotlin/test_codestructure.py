# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the Kotlin AST Parser."""

from __future__ import annotations

import pytest

from specweaver.loom.commons.language.interfaces import CodeStructureError
from specweaver.loom.commons.language.kotlin.codestructure import KotlinCodeStructure


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
@JvmStatic
@Throws(Exception::class)
fun annotatedFunc() { }
"""
    target_fn = parser.extract_symbol(code, "annotatedFunc")
    assert "@JvmStatic" in target_fn
    assert "@Throws" in target_fn


def test_extract_symbol_malformed_syntax(parser: KotlinCodeStructure) -> None:
    code = """fun broken(::: {{}

fun good(): Boolean { return true }"""
    try:
        target = parser.extract_symbol(code, "good")
        assert "fun good" in target
    except CodeStructureError:
        pass


def test_extract_symbol_scope_collision(parser: KotlinCodeStructure) -> None:
    code = """
class Parent { fun target() {} }
fun target() {}
"""
    target = parser.extract_symbol(code, "target")
    assert "target" in target
