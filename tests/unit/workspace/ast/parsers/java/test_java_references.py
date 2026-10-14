# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place a name occurs in one Java file, and what it is there.

Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a class: declaration, constructor, import, type uses; a method: declaration and calls |
| Boundary | a static import; a qualified type; a call inside an anonymous class; a method reference |
| Degradation | a file with a syntax error still gives references |
| Hostile | the name as a string; a field or parameter of the same name |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure

_CODE = """package app;

import app.util.Greeter;
import static app.util.Greeter.hello;
import java.util.*;

public class Loud extends Greeter implements Runnable {
    private int greet = 1;
    public Loud() { super(); }
    @Override
    public String greet(String n) {
        return greet(n) + this.greet(n) + super.greet(n) + Greeter.greet(n) + g.greet(n);
    }
    void f(int greet) {
        String s = "greet";
        Runnable r = new Runnable() { public void run() { greet(); } };
        Object x = Greeter::greet;
        app.util.Greeter q = new Greeter();
    }
}
"""


@pytest.fixture
def parser() -> JavaCodeStructure:
    return JavaCodeStructure()


def _by_line(refs):  # type: ignore[no-untyped-def]
    return [(r.kind, r.line) for r in refs]


def test_a_method_name_in_every_role(parser: JavaCodeStructure) -> None:
    refs = parser.find_references(_CODE, "greet")
    kinds = _by_line(refs)

    assert ("field", 8) in kinds
    assert ("definition", 11) in kinds
    assert [k for k in kinds if k[1] == 12] == [
        ("call", 12),
        ("attribute", 12),
        ("attribute", 12),
        ("attribute", 12),
        ("attribute", 12),
    ]
    assert ("field", 14) in kinds
    assert ("string", 15) in kinds
    assert ("call", 16) in kinds
    assert ("attribute", 17) in kinds

    line12 = [r for r in refs if r.line == 12]
    assert [r.receiver for r in line12[1:]] == ["this", "super", "Greeter", "g"]
    assert line12[0].owner == "Loud"
    definition = next(r for r in refs if r.kind == "definition")
    assert (definition.owner, definition.scope) == ("Loud", "class")


def test_a_call_in_an_anonymous_class_is_marked(parser: JavaCodeStructure) -> None:
    (call,) = [r for r in parser.find_references(_CODE, "greet") if r.line == 16]
    assert call.binding == "anonymous"


def test_a_class_name_in_every_role(parser: JavaCodeStructure) -> None:
    refs = parser.find_references(_CODE, "Greeter")
    kinds = _by_line(refs)

    assert ("import", 3) in kinds
    assert ("import", 4) in kinds
    assert ("type", 7) in kinds
    assert ("bare", 12) in kinds
    assert ("bare", 17) in kinds
    assert [k for k in kinds if k[1] == 18] == [("type", 18), ("type", 18)]

    imports = [r for r in refs if r.kind == "import"]
    assert [(r.qualifier, r.scope) for r in imports] == [
        ("app.util", "last"),
        ("app.util", "inner"),
    ]
    qualified = next(r for r in refs if r.line == 18)
    assert qualified.qualifier == "app.util"


def test_a_constructor_is_its_own_kind(parser: JavaCodeStructure) -> None:
    refs = parser.find_references(_CODE, "Loud")
    assert [(r.kind, r.line, r.owner) for r in refs] == [
        ("definition", 7, None),
        ("constructor", 9, "Loud"),
    ]


def test_spans_cover_exactly_the_name(parser: JavaCodeStructure) -> None:
    for name in ("greet", "Greeter", "Loud"):
        for ref in parser.find_references(_CODE, name):
            if ref.kind not in ("string", "text"):
                assert _CODE.encode()[ref.start_byte : ref.end_byte] == name.encode()


def test_a_local_receiver_is_marked_local(parser: JavaCodeStructure) -> None:
    code = "class A { void f(Greeter g) { g.greet(); Greeter.greet(); } }"
    attrs = [r for r in parser.find_references(code, "greet") if r.kind == "attribute"]
    assert [(r.receiver, r.receiver_binding) for r in attrs] == [
        ("g", "local"),
        ("Greeter", "free"),
    ]


def test_file_bindings(parser: JavaCodeStructure) -> None:
    facts = parser.file_bindings(_CODE)

    assert facts.package == "app"
    assert facts.imports == {"Greeter": ("app.util", "Greeter")}
    assert facts.statics == {"hello": ("app.util.Greeter", "hello")}
    assert facts.wildcards == ["java.util"]
    assert facts.defs == {"Loud"}
    assert facts.bases == {"Loud": ["Greeter", "Runnable"]}


def test_a_syntax_error_still_gives_references(parser: JavaCodeStructure) -> None:
    refs = parser.find_references("class A { void f( { greet(); } }", "greet")
    assert any(r.kind == "call" for r in refs)


def test_comments_hold_text_mentions(parser: JavaCodeStructure) -> None:
    refs = parser.find_references("// greet here\n/* and greet */\nclass A {}", "greet")
    assert _by_line(refs) == [("text", 1), ("text", 2)]
