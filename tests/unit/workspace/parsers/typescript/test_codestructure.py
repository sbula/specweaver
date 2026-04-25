# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the TypeScript AST Parser."""

from __future__ import annotations

import pytest

from specweaver.workspace.parsers.interfaces import CodeStructureError
from specweaver.workspace.parsers.typescript.codestructure import TypeScriptCodeStructure


@pytest.fixture
def parser() -> TypeScriptCodeStructure:
    return TypeScriptCodeStructure()


def test_extract_skeleton_strips_bodies(parser: TypeScriptCodeStructure) -> None:
    code = """
import { resolve } from 'path';

export function myFunc(a: number): string {
    console.log("Should be stripped");
    return "X";
}

export class MyClass {
    public method(): number {
        let y = 2;
        return y;
    }
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "import { resolve } from 'path';" in skeleton
    assert "export function myFunc(a: number): string {" in skeleton
    assert "export class MyClass {" in skeleton
    assert "public method(): number {" in skeleton
    assert "{ ... }" in skeleton
    assert "Should be stripped" not in skeleton
    assert "y = 2" not in skeleton


def test_extract_skeleton_preserves_docstrings(parser: TypeScriptCodeStructure) -> None:
    code = """
/**
 * This is a TS docstring.
 */
function myFunc() {
    let x = 10;
    return x;
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "function myFunc() {" in skeleton
    assert "This is a TS docstring." in skeleton
    assert "x = 10" not in skeleton
    assert "{ ... }" in skeleton


def test_extract_skeleton_empty_string(parser: TypeScriptCodeStructure) -> None:
    assert parser.extract_skeleton("") == ""
    assert parser.extract_skeleton("   ") == "   "


def test_extract_symbol_success(parser: TypeScriptCodeStructure) -> None:
    code = """
function func1() {
    console.log("1");
}

export class TargetClass {
    public method() {
        return true;
    }
}

export function TargetFunc() {
    return "success";
}
"""

    target_cls = parser.extract_symbol(code, "TargetClass")
    assert "class TargetClass {" in target_cls
    assert "public method() {" in target_cls
    assert "return true" in target_cls
    assert "func1" not in target_cls

    target_fn = parser.extract_symbol(code, "TargetFunc")
    assert "function TargetFunc() {" in target_fn
    assert 'return "success";' in target_fn
    assert "TargetClass" not in target_fn


def test_extract_symbol_not_found(parser: TypeScriptCodeStructure) -> None:
    code = "function existing() {}"

    with pytest.raises(CodeStructureError, match=r"Symbol \'Missing\' not found in the AST\."):
        parser.extract_symbol(code, "Missing")


def test_extract_symbol_empty_string(parser: TypeScriptCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match=r"Cannot extract \'Anything\' from empty code\."):
        parser.extract_symbol("", "Anything")


def test_extract_symbol_arrow_function(parser: TypeScriptCodeStructure) -> None:
    code = "export const MyArrowFunc = async () => { return 1; }"
    target = parser.extract_symbol(code, "MyArrowFunc")
    assert "export const MyArrowFunc" in target
    assert "=>" in target


def test_extract_symbol_export_wrappers(parser: TypeScriptCodeStructure) -> None:
    code = "export default class ExportedClass { }"
    target = parser.extract_symbol(code, "ExportedClass")
    assert "export default class ExportedClass" in target


def test_extract_symbol_malformed_syntax(parser: TypeScriptCodeStructure) -> None:
    code = """export default function broken(;::::)

export function good() { return true; }"""
    try:
        target = parser.extract_symbol(code, "good")
        assert "export function good" in target
    except CodeStructureError:
        pass  # Graceful failure is expected if severely malformed AST drops the symbol


def test_list_and_extract_dot_notation(parser: TypeScriptCodeStructure) -> None:
    code = """
    class Database {
        public connect() {
            return;
        }
    }

    class Inner {
        public query() {
        }
    }
    """
    symbols = parser.list_symbols(code)
    assert "Database" in symbols
    assert "Database.connect" in symbols
    assert "Inner" in symbols
    assert "Inner.query" in symbols

    target = parser.extract_symbol(code, "Database.connect")
    assert "public connect()" in target
    assert "class Database" not in target


def test_extract_symbol_scope_collision(parser: TypeScriptCodeStructure) -> None:
    code = """
class Parent { target() { return 1; } }
function target() { return 2; }
"""
    target = parser.extract_symbol(code, "Parent.target")
    assert "target() { return 1; }" in target


def test_extract_framework_markers_success(parser: TypeScriptCodeStructure) -> None:
    code = """
@Component
@Controller("/api")
export class MyController extends BaseController implements InterfaceA, InterfaceB {
    @Field
    public method() { }
}
"""
    markers = parser.extract_framework_markers(code)

    assert "MyController" in markers
    assert "Component" in markers["MyController"]["decorators"]
    assert 'Controller("/api")' in markers["MyController"]["decorators"]
    assert "BaseController" in markers["MyController"]["extends"]
    assert "InterfaceA" in markers["MyController"]["extends"]
    assert "InterfaceB" in markers["MyController"]["extends"]

    assert "MyController.method" in markers
    assert "Field" in markers["MyController.method"]["decorators"]
    assert "extends" not in markers["MyController.method"]


def test_extract_framework_markers_empty(parser: TypeScriptCodeStructure) -> None:
    code = "class Simple {}"
    markers = parser.extract_framework_markers(code)
    assert markers == {"Simple": {"decorators": [], "extends": []}}


def test_list_symbols_decorator_filter(parser: TypeScriptCodeStructure) -> None:
    code = """
@Component
export class MyController {
    public method() { }
}

export class OtherController {
    public method() { }
}
"""
    symbols = parser.list_symbols(code, decorator_filter="Component")
    assert "MyController" in symbols
    assert "OtherController" not in symbols
