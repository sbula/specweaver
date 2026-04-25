# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the Go AST Parser."""

from __future__ import annotations

import pytest

from specweaver.workspace.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.parsers.interfaces import CodeStructureError


@pytest.fixture
def parser() -> GoCodeStructure:
    return GoCodeStructure()


def test_extract_skeleton_strips_bodies(parser: GoCodeStructure) -> None:
    code = """
package main

import "fmt"

func myFunc(a int) string {
    fmt.Println("Should be stripped")
    return "X"
}

type MyStruct struct {
    Val int
}

func (m *MyStruct) Method() {
    y := 2
    _ = y
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "import \"fmt\"" in skeleton
    assert "func myFunc(a int) string {" in skeleton
    assert "type MyStruct struct {" in skeleton
    assert "func (m *MyStruct) Method() {" in skeleton
    assert "..." in skeleton
    assert "Should be stripped" not in skeleton
    assert "y := 2" not in skeleton


def test_extract_skeleton_empty_string(parser: GoCodeStructure) -> None:
    assert parser.extract_skeleton("") == ""
    assert parser.extract_skeleton("   ") == "   "


def test_extract_symbol_success(parser: GoCodeStructure) -> None:
    code = """
package main

import "fmt"

func func1() {
    fmt.Println("1")
}

type TargetStruct struct {}

func (t *TargetStruct) Method() bool {
    return true
}

func TargetFunc() string {
    return "success"
}
"""

    target_cls = parser.extract_symbol(code, "TargetStruct")
    assert "type TargetStruct struct {}" in target_cls
    assert "Method" not in target_cls

    target_method = parser.extract_symbol(code, "TargetStruct.Method")
    assert "func (t *TargetStruct) Method() bool {" in target_method
    assert "return true" in target_method

    target_fn = parser.extract_symbol(code, "TargetFunc")
    assert "func TargetFunc() string {" in target_fn
    assert "return \"success\"" in target_fn
    assert "TargetStruct" not in target_fn


def test_extract_symbol_not_found(parser: GoCodeStructure) -> None:
    code = "func existing() {}"

    with pytest.raises(CodeStructureError, match=r"Symbol \'Missing\' not found in the AST\."):
        parser.extract_symbol(code, "Missing")


def test_extract_symbol_empty_string(parser: GoCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match=r"Cannot extract \'Anything\' from empty code\."):
        parser.extract_symbol("", "Anything")


def test_extract_symbol_malformed_syntax(parser: GoCodeStructure) -> None:
    code = """func existing( {
}

func Good() bool { return true }"""
    try:
        target = parser.extract_symbol(code, "Good")
        assert "func Good() bool" in target
    except CodeStructureError:
        pass


def test_extract_symbol_scope_collision(parser: GoCodeStructure) -> None:
    code = """
type Parent struct {}
func (p *Parent) Collide() int { return 1 }
func Collide() int { return 2 }
"""
    target1 = parser.extract_symbol(code, "Parent.Collide")
    assert "func (p *Parent) Collide() int" in target1

    target2 = parser.extract_symbol(code, "Collide")
    assert "func Collide() int" in target2


def test_list_and_extract_dot_notation(parser: GoCodeStructure) -> None:
    code = """
package main

type Database struct {}

func (d *Database) Connect() bool {
    return true
}
"""
    symbols = parser.list_symbols(code)
    assert "Database" in symbols
    assert "Database.Connect" in symbols

    target = parser.extract_symbol(code, "Database.Connect")
    assert "func (d *Database) Connect() bool" in target
    assert "type Database struct" not in target


def test_extract_framework_markers_empty(parser: GoCodeStructure) -> None:
    code = "func simple() {}"
    markers = parser.extract_framework_markers(code)
    assert markers == {}


def test_list_symbols_visibility_filter(parser: GoCodeStructure) -> None:
    code = """
package main

type MyStruct struct {}

func (m *MyStruct) PublicMethod() {}
func (m *MyStruct) privateMethod() {}

func PublicFunc() {}
func privateFunc() {}
"""
    symbols = parser.list_symbols(code, visibility=["public"])
    assert "MyStruct" in symbols
    assert "MyStruct.PublicMethod" in symbols
    assert "PublicFunc" in symbols
    assert "MyStruct.privateMethod" not in symbols
    assert "privateFunc" not in symbols


def test_extract_imports(parser: GoCodeStructure) -> None:
    code = """
package main

import "fmt"
import (
    "os"
    "strings"
)
"""
    imports = parser.extract_imports(code)
    assert "fmt" in imports
    assert "os" in imports
    assert "strings" in imports


def test_replace_symbol_success(parser: GoCodeStructure) -> None:
    code = "func old() {}\n"
    new_code = "func new() {\n    return 42\n}"
    result = parser.replace_symbol(code, "old", new_code)
    assert "func new()" in result
    assert "func old()" not in result


def test_add_symbol_success(parser: GoCodeStructure) -> None:
    code = "package main\n\nfunc existing() {}"
    new_code = "func new() {}"
    result = parser.add_symbol(code, None, new_code)
    assert "func existing() {}" in result
    assert "func new() {}" in result

def test_extract_grouped_type_block(parser: GoCodeStructure) -> None:
    code = """
package main

type (
    A struct {
        val int
    }
    B interface {
        Do()
    }
)
"""
    target_a = parser.extract_symbol(code, "A")
    assert "A struct {" in target_a
    assert "B interface" not in target_a
    assert "type (" not in target_a

def test_replace_grouped_type_block(parser: GoCodeStructure) -> None:
    code = """
package main
type (
    A struct {}
    B struct {}
)
"""
    new_code = "A struct { val int }"
    result = parser.replace_symbol(code, "A", new_code)
    assert "A struct { val int }" in result
    assert "B struct {}" in result
    assert "type (" in result

def test_extract_interface(parser: GoCodeStructure) -> None:
    code = "package main\n\ntype B interface {\n\tDo()\n}"
    target = parser.extract_symbol(code, "B")
    assert "type B interface" in target
    assert "Do()" in target

def test_add_symbol_no_trailing_newline(parser: GoCodeStructure) -> None:
    code = "package main\nfunc existing() {}"
    new_code = "func new() {}"
    result = parser.add_symbol(code, None, new_code)
    assert result == code + "\n\n" + new_code

def test_supported_intents(parser: GoCodeStructure) -> None:
    intents = parser.supported_intents()
    assert "traceability" in intents
    assert "imports" in intents
    assert "skeleton" in intents

def test_supported_parameters(parser: GoCodeStructure) -> None:
    assert parser.supported_parameters() == ["visibility"]

def test_binary_ignores(parser: GoCodeStructure) -> None:
    assert "*.o" in parser.get_binary_ignore_patterns()
    assert "*.exe" in parser.get_binary_ignore_patterns()

def test_directory_ignores(parser: GoCodeStructure) -> None:
    assert "bin/" in parser.get_default_directory_ignores()
