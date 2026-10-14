# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Rust rename planned across a crate's modules: every proven use, or nothing.

Proves: D-SENS-06 FR-7
Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a struct through `use` and paths; a free function; an inherent method; a trait method family |
| Boundary | a use list with `as`; `super::` and `self::`; a `pub use` re-export; `mod.rs` |
| Degradation | a glob use; a trait from outside the crate; the name in a macro; an inline module |
| Hostile | an unknown receiver; a local of the name; a keyword new name; the name as a string |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.refactor.rename import RenamePlan, RenameRefusal, Spot, plan_rename

_RS = RustCodeStructure()

_CRATE = {
    "Cargo.toml": '[package]\nname = "app"\n',
    "src/lib.rs": "pub mod util;\nmod run;\n",
    "src/util.rs": (
        "pub struct Greeter;\n"
        "impl Greeter {\n"
        "    pub fn greet(&self) -> u32 { 1 }\n"
        "    pub fn twice(&self) -> u32 { self.greet() + Self::greet(self) }\n"
        "}\n"
        "pub fn total(a: u32) -> u32 { a }\n"
    ),
    "src/run.rs": (
        "use crate::util::{Greeter, total as sum};\n"
        "pub fn go() -> u32 {\n"
        "    let g = Greeter;\n"
        "    Greeter::greet(&g) + sum(1) + crate::util::total(2)\n"
        "}\n"
    ),
}

_TRAITS = {
    "Cargo.toml": '[package]\nname = "app"\n',
    "src/lib.rs": "mod shape;\nmod square;\n",
    "src/shape.rs": "pub trait Shape {\n    fn area(&self) -> u32;\n    fn twice(&self) -> u32 { self.area() * 2 }\n}\n",
    "src/square.rs": (
        "use crate::shape::Shape;\n"
        "pub struct Square;\n"
        "impl Shape for Square {\n    fn area(&self) -> u32 { 4 }\n}\n"
        "pub fn f(s: &Square) -> u32 { Shape::area(s) }\n"
    ),
}


def _plan(files: dict[str, str], path: str, symbol: str, new: str) -> RenamePlan:
    result = plan_rename(files, path, symbol, new, _RS)
    assert isinstance(result, RenamePlan), result
    return result


def _refusal(files: dict[str, str], path: str, symbol: str, new: str) -> RenameRefusal:
    result = plan_rename(files, path, symbol, new, _RS)
    assert isinstance(result, RenameRefusal), result
    return result


# --- Happy -----------------------------------------------------------------------------------


def test_a_struct_through_use_and_paths() -> None:
    plan = _plan(_CRATE, "src/util.rs", "Greeter", "Welcomer")

    assert plan.changes["src/util.rs"].startswith("pub struct Welcomer;\nimpl Welcomer {")
    assert plan.changes["src/run.rs"].startswith("use crate::util::{Welcomer, total as sum};")
    assert "let g = Welcomer;" in plan.changes["src/run.rs"]
    assert "Welcomer::greet(&g)" in plan.changes["src/run.rs"]


def test_a_free_function_through_an_alias_and_a_full_path() -> None:
    plan = _plan(_CRATE, "src/util.rs", "total", "add")

    assert "pub fn add(a: u32)" in plan.changes["src/util.rs"]
    assert plan.changes["src/run.rs"].startswith("use crate::util::{Greeter, add as sum};")
    assert "sum(1) + crate::util::add(2)" in plan.changes["src/run.rs"]


def test_an_inherent_method_through_self_and_the_type() -> None:
    plan = _plan(_CRATE, "src/util.rs", "Greeter.greet", "hello")

    assert "self.hello() + Self::hello(self)" in plan.changes["src/util.rs"]
    assert "Greeter::hello(&g)" in plan.changes["src/run.rs"]


def test_a_trait_method_and_every_impl_of_it() -> None:
    plan = _plan(_TRAITS, "src/shape.rs", "Shape.area", "size")

    assert "fn size(&self) -> u32;" in plan.changes["src/shape.rs"]
    assert "self.size() * 2" in plan.changes["src/shape.rs"]
    assert "fn size(&self) -> u32 { 4 }" in plan.changes["src/square.rs"]
    assert "Shape::size(s)" in plan.changes["src/square.rs"]


def test_the_trait_family_is_found_from_an_impl_too() -> None:
    plan = _plan(_TRAITS, "src/square.rs", "Square.area", "size")
    assert sorted(plan.changes) == ["src/shape.rs", "src/square.rs"]


# --- Boundary --------------------------------------------------------------------------------


def test_super_self_mod_rs_and_a_re_export() -> None:
    files = {
        "Cargo.toml": '[package]\nname = "app"\n',
        "src/main.rs": "mod a;\nuse crate::a::Thing;\nfn main() { let _t = Thing; }\n",
        "src/a/mod.rs": "mod b;\npub use self::b::Thing;\n",
        "src/a/b.rs": "pub struct Thing;\nfn k() -> Thing { super::b::Thing }\n",
    }
    plan = _plan(files, "src/a/b.rs", "Thing", "Item")
    assert sorted(plan.changes) == ["src/a/b.rs", "src/a/mod.rs", "src/main.rs"]
    assert "super::b::Item" in plan.changes["src/a/b.rs"]


def test_a_same_named_struct_in_another_module_is_left_alone() -> None:
    files = {
        **_CRATE,
        "src/lib.rs": "pub mod util;\nmod run;\nmod other;\n",
        "src/other.rs": "struct Greeter;\nfn k() -> Greeter { Greeter }\n",
    }
    assert "src/other.rs" not in _plan(files, "src/util.rs", "Greeter", "Welcomer").changes


def test_an_outside_crate_path_is_left_alone() -> None:
    files = {**_CRATE, "src/run.rs": _CRATE["src/run.rs"] + "fn h() { std::mem::total(); }\n"}
    assert "std::mem::total" in _plan(files, "src/util.rs", "total", "add").changes["src/run.rs"]


# --- Degradation -----------------------------------------------------------------------------


def test_a_glob_use_is_unsure() -> None:
    files = {**_CRATE, "src/run.rs": "use crate::util::*;\npub fn go() -> u32 { total(1) }\n"}
    assert _refusal(files, "src/util.rs", "total", "add").spots == [Spot("src/run.rs", 2)]


def test_a_trait_from_outside_the_crate_refuses() -> None:
    files = {
        **_CRATE,
        "src/util.rs": _CRATE["src/util.rs"]
        + "impl std::fmt::Display for Greeter {\n    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result { Ok(()) }\n}\n",
    }
    assert "outside the project" in _refusal(files, "src/util.rs", "Greeter.fmt", "show").reason


def test_the_name_in_a_macro_is_unsure() -> None:
    files = {
        **_CRATE,
        "src/run.rs": _CRATE["src/run.rs"] + 'fn m() { println!("{}", total(3)); }\n',
    }
    assert _refusal(files, "src/util.rs", "total", "add").spots == [Spot("src/run.rs", 6)]


def test_an_item_in_an_inline_module_refuses() -> None:
    files = {**_CRATE, "src/util.rs": "pub mod inner {\n    pub fn deep() {}\n}\n"}
    assert "inline" in _refusal(files, "src/util.rs", "deep", "deeper").reason


# --- Hostile ---------------------------------------------------------------------------------


def test_an_unknown_receiver_is_unsure() -> None:
    files = {
        **_CRATE,
        "src/run.rs": _CRATE["src/run.rs"] + "fn n(x: &dyn Any) -> u32 { x.greet() }\n",
    }
    assert _refusal(files, "src/util.rs", "Greeter.greet", "hello").spots == [Spot("src/run.rs", 6)]


def test_a_local_of_the_name_is_left_alone() -> None:
    files = {
        **_CRATE,
        "src/run.rs": _CRATE["src/run.rs"] + "fn n() -> u32 { let total = 1; total }\n",
    }
    assert (
        "let total = 1; total" in _plan(files, "src/util.rs", "total", "add").changes["src/run.rs"]
    )


@pytest.mark.parametrize("new", ["fn", "struct", "self", "1x", ""])
def test_a_keyword_new_name_refuses(new: str) -> None:
    assert _refusal(_CRATE, "src/util.rs", "total", new).reason


def test_the_name_as_a_string_is_unsure() -> None:
    files = {**_CRATE, "src/run.rs": _CRATE["src/run.rs"] + 'const N: &str = "total";\n'}
    assert _refusal(files, "src/util.rs", "total", "add").spots == [Spot("src/run.rs", 6)]


def test_an_inherent_method_also_given_by_a_trait_refuses() -> None:
    files = {
        **_CRATE,
        "src/lib.rs": "pub mod util;\nmod run;\nmod extra;\n",
        "src/extra.rs": (
            "use crate::util::Greeter;\npub trait Hello { fn greet(&self) -> u32; }\n"
            "impl Hello for Greeter {\n    fn greet(&self) -> u32 { 2 }\n}\n"
        ),
    }
    assert "from the trait" in _refusal(files, "src/util.rs", "Greeter.greet", "hello").reason


def test_a_local_shadowing_the_item_in_its_own_file_is_left_alone() -> None:
    files = {
        **_CRATE,
        "src/util.rs": _CRATE["src/util.rs"] + "fn n() -> u32 { let total = 1; total }\n",
    }
    plan = _plan(files, "src/util.rs", "total", "add")
    assert "let total = 1; total }" in plan.changes["src/util.rs"]
    assert "pub fn add(a: u32)" in plan.changes["src/util.rs"]
