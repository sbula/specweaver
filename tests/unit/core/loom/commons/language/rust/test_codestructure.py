# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the Rust AST Parser."""

from __future__ import annotations

import pytest

from specweaver.core.loom.commons.language.interfaces import CodeStructureError
from specweaver.core.loom.commons.language.rust.codestructure import RustCodeStructure


@pytest.fixture
def parser() -> RustCodeStructure:
    return RustCodeStructure()


def test_extract_skeleton_strips_bodies(parser: RustCodeStructure) -> None:
    code = """
use std::fmt;

pub struct MyStruct {
    a: i32,
}

impl MyStruct {
    pub fn method(&self) -> i32 {
        let y = 2;
        return y;
    }
}

pub fn standalone() -> String {
    println!("Should be stripped");
    return String::from("X");
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "use std::fmt;" in skeleton
    assert "pub struct MyStruct {" in skeleton
    assert "pub fn method(&self) -> i32 {" in skeleton
    assert "pub fn standalone() -> String {" in skeleton
    assert "{ ... }" in skeleton
    assert "Should be stripped" not in skeleton
    assert "y = 2" not in skeleton


def test_extract_skeleton_preserves_docstrings(parser: RustCodeStructure) -> None:
    code = """
/// This is a rust docstring.
pub fn my_func() {
    let x = 10;
    return x;
}
"""
    skeleton = parser.extract_skeleton(code)

    assert "pub fn my_func() {" in skeleton
    assert "/// This is a rust docstring." in skeleton
    assert "x = 10" not in skeleton
    assert "{ ... }" in skeleton


def test_extract_skeleton_empty_string(parser: RustCodeStructure) -> None:
    assert parser.extract_skeleton("") == ""
    assert parser.extract_skeleton("   ") == "   "


def test_extract_symbol_success_struct_and_impl(parser: RustCodeStructure) -> None:
    code = """
pub struct TargetStruct {
    pub value: bool,
}

impl TargetStruct {
    pub fn do_thing(&self) {
        println!("success");
    }
}

pub fn some_other_func() {}
"""

    target_cls = parser.extract_symbol(code, "TargetStruct")
    assert "pub struct TargetStruct {" in target_cls
    assert "pub value: bool," in target_cls
    assert "impl TargetStruct {" in target_cls
    assert "pub fn do_thing(&self) {" in target_cls
    assert "some_other_func" not in target_cls


def test_extract_symbol_success_function(parser: RustCodeStructure) -> None:
    code = """
pub fn TargetFunc() {
    return "success";
}
"""
    target_fn = parser.extract_symbol(code, "TargetFunc")
    assert "pub fn TargetFunc() {" in target_fn
    assert 'return "success";' in target_fn


def test_extract_symbol_not_found(parser: RustCodeStructure) -> None:
    code = "fn existing() {}"

    with pytest.raises(CodeStructureError, match=r"Symbol \'Missing\' not found in the AST\."):
        parser.extract_symbol(code, "Missing")


def test_extract_symbol_empty_string(parser: RustCodeStructure) -> None:
    with pytest.raises(CodeStructureError, match=r"Cannot extract \'Anything\' from empty code\."):
        parser.extract_symbol("", "Anything")


def test_extract_symbol_traits_and_generics(parser: RustCodeStructure) -> None:
    code = """
pub struct GenStruct<T> { x: T }

impl<T> GenStruct<T> {
    fn base() {}
}

impl<T> std::fmt::Display for GenStruct<T> {
    fn fmt() {}
}
"""
    target = parser.extract_symbol(code, "GenStruct")
    assert "impl<T> GenStruct<T>" in target
    assert "impl<T> std::fmt::Display for GenStruct<T>" in target
    assert "fn fmt() {}" in target


def test_extract_symbol_malformed_syntax(parser: RustCodeStructure) -> None:
    code = """fn broken(:: -> { }

fn good() -> bool { true }"""
    try:
        target = parser.extract_symbol(code, "good")
        assert "fn good() -> bool" in target
    except CodeStructureError:
        pass


def test_extract_symbol_scope_collision(parser: RustCodeStructure) -> None:
    code = """
struct Target {}
impl Target { fn target() {} }
"""
    # Wait, if we search for target, it should find it at least!
    target = parser.extract_symbol(code, "Target")
    assert "Target" in target


def test_extract_framework_markers_success(parser: RustCodeStructure) -> None:
    code = """
#[derive(Debug, Serialize)]
#[actix_web::get("/api")]
pub struct MyController;

impl BaseController for MyController {}
impl Other for MyController {}

#[my_macro]
pub fn standalone() {}
"""
    markers = parser.extract_framework_markers(code)

    assert "MyController" in markers
    assert "derive(Debug, Serialize)" in markers["MyController"]["decorators"] or "derive" in markers["MyController"]["decorators"]
    # We should at least capture the macro paths or full texts:
    found_actix = any("actix_web" in d for d in markers["MyController"]["decorators"])
    assert found_actix

    assert "BaseController" in markers["MyController"]["extends"]
    assert "Other" in markers["MyController"]["extends"]

    assert "standalone" in markers
    assert "my_macro" in markers["standalone"]["decorators"]
    assert "extends" not in markers["standalone"]


def test_extract_framework_markers_empty(parser: RustCodeStructure) -> None:
    code = "struct Simple {}"
    markers = parser.extract_framework_markers(code)
    assert markers == {"Simple": {"decorators": [], "extends": []}}
