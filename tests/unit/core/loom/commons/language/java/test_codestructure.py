# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the Java AST Parser."""

from __future__ import annotations

import pytest

from specweaver.core.loom.commons.language.interfaces import CodeStructureError
from specweaver.core.loom.commons.language.java.codestructure import JavaCodeStructure


@pytest.fixture
def parser() -> JavaCodeStructure:
    return JavaCodeStructure()


def test_extract_skeleton_strips_bodies(parser: JavaCodeStructure) -> None:
    code = """
package com.example;

public class MyClass {
    public MyClass() {
        System.out.println("Init");
    }

    public void method(int x) {
        int y = x + 2;
        return;
    }
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "package com.example;" in skeleton
    assert "public class MyClass {" in skeleton
    assert "public MyClass() {" in skeleton
    assert "public void method(int x) {" in skeleton
    assert "{ ... }" in skeleton
    assert 'System.out.println("Init")' not in skeleton
    assert "int y =" not in skeleton


def test_extract_skeleton_preserves_docstrings(parser: JavaCodeStructure) -> None:
    code = """
/**
 * This is a java docstring.
 */
public void myFunc() {
    int x = 10;
    return;
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "public void myFunc() {" in skeleton
    assert "This is a java docstring." in skeleton
    assert "int x = 10" not in skeleton
    assert "{ ... }" in skeleton


def test_extract_skeleton_empty_string(parser: JavaCodeStructure) -> None:
    assert parser.extract_skeleton("") == ""
    assert parser.extract_skeleton("   ") == "   "


def test_extract_symbol_success(parser: JavaCodeStructure) -> None:
    code = """
public class TargetClass {
    public boolean value;

    public void do_thing() {
        System.out.println("success");
    }
}

public interface TargetInterface {
    void process();
}
"""

    target_cls = parser.extract_symbol(code, "TargetClass")
    assert "public class TargetClass {" in target_cls
    assert "public boolean value;" in target_cls
    assert "public void do_thing() {" in target_cls
    assert "TargetInterface" not in target_cls

    target_inter = parser.extract_symbol(code, "TargetInterface")
    assert "public interface TargetInterface {" in target_inter
    assert "void process();" in target_inter


def test_extract_symbol_not_found(parser: JavaCodeStructure) -> None:
    code = "public class existing {}"

    with pytest.raises(CodeStructureError, match=r"Symbol \'Missing\' not found in the AST\."):
        parser.extract_symbol(code, "Missing")


def test_extract_symbol_empty_string(parser: JavaCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match=r"Cannot extract \'Anything\' from empty code\."):
        parser.extract_symbol("", "Anything")


def test_extract_symbol_annotation_preservation(parser: JavaCodeStructure) -> None:
    code = """
@RestController
@RequestMapping("/api")
public class AnnotatedClass {
    @Override
    @Transactional
    public void method() { }
}
"""
    target_cls = parser.extract_symbol(code, "AnnotatedClass")
    assert "@RestController" in target_cls

    target_fn = parser.extract_symbol(code, "method")
    assert "@Override" in target_fn
    assert "@Transactional" in target_fn


def test_extract_symbol_malformed_syntax(parser: JavaCodeStructure) -> None:
    code = """public class Broken { public void broken(((( { } }

public class Good { public boolean good() { return true; } }"""
    try:
        target = parser.extract_symbol(code, "Good")
        assert "class Good" in target
    except CodeStructureError:
        pass


def test_extract_symbol_scope_collision(parser: JavaCodeStructure) -> None:
    code = """
public class Parent { public void target() {} }
public interface Other { void target(); }
"""
    target = parser.extract_symbol(code, "target")
    assert "target" in target


def test_extract_symbol_missing_closing_brackets(parser: JavaCodeStructure) -> None:
    code = """
public class UnclosedClass {
    public void unclosedMethod() {
        System.out.println("Wait, I never closed the class or the method...
"""
    try:
        # It shouldn't crash SpecWeaver, it should just fail to find a valid AST symbol boundary
        # or it should recover and extract it anyway!
        target = parser.extract_symbol(code, "UnclosedClass")
        assert "UnclosedClass" in target
    except CodeStructureError:
        pass  # Graceful failure is also acceptable for catastrophic syntax loss without crashing the runner
