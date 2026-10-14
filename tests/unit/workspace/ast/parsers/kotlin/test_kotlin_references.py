# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place a name occurs in one Kotlin file, and what it is there.

Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a class: declaration, import, type and constructor call; a method: declaration and calls |
| Boundary | an import alias; a qualified type; callable references; an object literal |
| Degradation | a file with a syntax error still gives references |
| Hostile | the name as a string, a named argument, a parameter, a lambda parameter |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure

_CODE = """package app

import app.util.Greeter
import app.util.Other as O
import java.util.*

class Loud(val x: Int) : Greeter(), Runnable {
    override fun greet(n: String): String {
        return greet(n) + this.greet(n) + super.greet(n) + g.greet(n) + Greeter().greet(n)
    }
    fun f(greet: Int) {
        val s = "greet"
        f(greet = 1)
        val r = Greeter::greet
        val o = object : Runnable { override fun run() { greet("x") } }
        val q: app.util.Greeter? = null
    }
}

fun top() = Loud(1)
"""


@pytest.fixture
def parser() -> KotlinCodeStructure:
    return KotlinCodeStructure()


def _kinds(refs):  # type: ignore[no-untyped-def]
    return [(r.kind, r.line) for r in refs]


def test_a_method_name_in_every_role(parser: KotlinCodeStructure) -> None:
    refs = parser.find_references(_CODE, "greet")
    kinds = _kinds(refs)

    assert ("definition", 8) in kinds
    assert [k for k in kinds if k[1] == 9] == [("call", 9)] + [("attribute", 9)] * 4
    assert [r.receiver for r in refs if r.line == 9][1:] == ["this", "super", "g", "Greeter()"]
    assert ("field", 11) in kinds
    assert ("string", 12) in kinds
    assert ("keyword", 13) in kinds
    assert ("attribute", 14) in kinds
    (anonymous,) = [r for r in refs if r.line == 15]
    assert (anonymous.kind, anonymous.binding) == ("call", "anonymous")
    definition = next(r for r in refs if r.kind == "definition")
    assert (definition.scope, definition.owner) == ("class", "Loud")


def test_a_class_name_in_every_role(parser: KotlinCodeStructure) -> None:
    refs = parser.find_references(_CODE, "Greeter")
    kinds = _kinds(refs)

    assert ("import", 3) in kinds
    assert ("type", 7) in kinds
    assert ("call", 9) in kinds
    assert ("bare", 14) in kinds
    qualified = next(r for r in refs if r.line == 16)
    assert (qualified.kind, qualified.qualifier) == ("type", "app.util")
    imp = next(r for r in refs if r.kind == "import")
    assert (imp.qualifier, imp.scope) == ("app.util", "last")


def test_a_top_level_function_is_a_module_definition(parser: KotlinCodeStructure) -> None:
    (top,) = parser.find_references(_CODE, "top")
    assert (top.kind, top.scope, top.owner) == ("definition", "module", None)


def test_spans_cover_exactly_the_name(parser: KotlinCodeStructure) -> None:
    for name in ("greet", "Greeter", "Loud"):
        for r in parser.find_references(_CODE, name):
            if r.kind not in ("string", "text"):
                assert _CODE.encode()[r.start_byte : r.end_byte] == name.encode()


def test_a_lambda_parameter_shadows_and_a_receiver_can_be_local(
    parser: KotlinCodeStructure,
) -> None:
    code = "fun f(g: Greeter) { g.greet(); val l = { greet: Int -> greet } }"
    refs = parser.find_references(code, "greet")
    attribute = next(r for r in refs if r.kind == "attribute")

    assert attribute.receiver_binding == "local"
    assert [r.binding for r in refs if r.kind == "bare"] == ["local"]


def test_file_bindings(parser: KotlinCodeStructure) -> None:
    facts = parser.file_bindings(_CODE)

    assert facts.package == "app"
    assert facts.imports == {"Greeter": ("app.util", "Greeter"), "O": ("app.util", "Other")}
    assert facts.wildcards == ["java.util"]
    assert facts.defs == {"Loud", "top"}
    assert facts.bases == {"Loud": ["Greeter", "Runnable"]}


def test_a_syntax_error_still_gives_references(parser: KotlinCodeStructure) -> None:
    code = "class A { fun f() { greet() } fun g( }"
    assert any(r.kind == "call" for r in parser.find_references(code, "greet"))


def test_comments_hold_text_mentions(parser: KotlinCodeStructure) -> None:
    refs = parser.find_references("// greet\n/* greet */\nclass A", "greet")
    assert _kinds(refs) == [("text", 1), ("text", 2)]
