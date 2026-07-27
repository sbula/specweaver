# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the Java AST Parser."""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure


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
    public class TargetClass {
        @Override
        @SuppressWarnings("unchecked")
        public void method() {
            return;
        }
    }
    """
    target_fn = parser.extract_symbol(code, "TargetClass.method")
    assert "@Override" in target_fn
    assert '@SuppressWarnings("unchecked")' in target_fn
    assert "public void method()" in target_fn


def test_extract_symbol_malformed_syntax(parser: JavaCodeStructure) -> None:
    code = """public class Broken { public void broken(((( { } }

public class Good { public boolean good() { return true; } }"""
    try:
        target = parser.extract_symbol(code, "Good")
        assert "class Good" in target
    except CodeStructureError:
        pass


def test_extract_symbol_enum(parser: JavaCodeStructure) -> None:
    code = """
    public enum Status {
        ACTIVE,
        INACTIVE
    }
    """
    target = parser.extract_symbol(code, "Status")
    assert "enum Status" in target
    assert "ACTIVE," in target


def test_list_and_extract_dot_notation(parser: JavaCodeStructure) -> None:
    code = """
    public class Database {
        public void connect() {
            return;
        }

        public class Inner {
            public void query() {
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
    assert "public void connect()" in target
    assert "class Database" not in target


def test_extract_symbol_scope_collision(parser: JavaCodeStructure) -> None:
    code = """
public class Parent { public void target() {} }
public class Other { public void target() {} }
"""
    # We expect no crashes, should grab one of them predictably based on exact scope
    target = parser.extract_symbol(code, "Parent.target")
    assert "public void target() {}" in target


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


def test_extract_framework_markers_success(parser: JavaCodeStructure) -> None:
    code = """
@RestController
@RequestMapping("/api")
public class AnnotatedClass extends BaseController implements Serializable, Cloneable {
    @Override
    @Transactional
    public void myMethod() { }
}
"""
    markers = parser.extract_framework_markers(code)

    assert "AnnotatedClass" in markers
    assert markers["AnnotatedClass"]["decorators"] == ["RestController", 'RequestMapping("/api")']
    assert markers["AnnotatedClass"]["extends"] == ["BaseController", "Serializable", "Cloneable"]

    assert "AnnotatedClass.myMethod" in markers
    assert markers["AnnotatedClass.myMethod"]["decorators"] == ["Override", "Transactional"]
    assert "extends" not in markers["AnnotatedClass.myMethod"]


def test_extract_framework_markers_empty(parser: JavaCodeStructure) -> None:
    code = "public class Simple {}"
    markers = parser.extract_framework_markers(code)
    assert markers == {"Simple": {"decorators": [], "extends": []}}


def test_list_symbols_decorator_filter(parser: JavaCodeStructure) -> None:
    code = """
@RestController
public class MyController {
    public void myMethod() { }
}

public class OtherController {
    public void otherMethod() { }
}
"""
    symbols = parser.list_symbols(code, decorator_filter="RestController")
    assert "MyController" in symbols
    assert "OtherController" not in symbols
