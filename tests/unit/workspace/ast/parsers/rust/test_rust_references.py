# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place a name occurs in one Rust file, and what it is there.

Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | an item, a use, a path, a method definition with its impl type and trait |
| Boundary | a use list with an alias; a glob; a `pub use` re-export |
| Degradation | a file with a syntax error still gives references |
| Hostile | the name in a macro, as a string, as a local pattern |
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure

_CODE = """use crate::util::{Greeter, total as sum};
use crate::x::*;
pub use self::y::Z;
impl Shape for Greeter {
    fn area(&self) -> u32 { self.area() + Self::area(self) + crate::util::area(1) }
}
fn f(area: u32) { let s = "area"; println!("{}", area); }
"""


def _kinds(refs):  # type: ignore[no-untyped-def]
    return [(r.kind, r.line) for r in refs]


def test_a_method_name_in_every_role() -> None:
    refs = RustCodeStructure().find_references(_CODE, "area")
    definition = refs[0]

    assert (definition.kind, definition.owner, definition.qualifier) == (
        "definition",
        "Greeter",
        "Shape",
    )
    assert [(r.kind, r.qualifier or r.receiver) for r in refs if r.line == 5][1:] == [
        ("attribute", "self"),
        ("path", "Self"),
        ("path", "crate::util"),
    ]
    assert ("field", 7) in _kinds(refs)
    assert ("string", 7) in _kinds(refs)
    assert [r.kind for r in refs if r.line == 7].count("string") == 2


def test_uses_with_their_qualifier_and_alias() -> None:
    refs = RustCodeStructure().find_references(_CODE, "total")
    assert [(r.kind, r.qualifier, r.alias) for r in refs] == [("import", "crate::util", "sum")]


def test_file_bindings() -> None:
    facts = RustCodeStructure().file_bindings(_CODE + "mod util;\npub struct Loud;\n")

    assert facts.imports["sum"] == ("crate::util::total", None)
    assert facts.statics == {"Z": ("self::y::Z", "")}
    assert facts.wildcards == ["crate::x"]
    assert facts.others == {"util"}
    assert {"f", "Loud"} <= facts.defs
    assert facts.bases == {"Greeter": ["Shape"]}


def test_a_syntax_error_still_gives_references() -> None:
    refs = RustCodeStructure().find_references("fn f( { area(); }\nfn g() { area(); }", "area")
    assert any(r.kind == "bare" for r in refs)
