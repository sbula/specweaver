# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place a name occurs in one TypeScript file, and what it is there.

Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a class: declaration, import, extends, `new`, type; a method: declaration and member calls |
| Boundary | a re-export; a namespace import; `this` inside a `function` expression; an abstract class |
| Degradation | a file with a syntax error still gives references |
| Hostile | an object-literal key, a shorthand property, a string, a local parameter |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

_CODE = """import { Greeter, other as o } from "./greeter";
import * as ns from "../lib/util";
export { Greeter as G } from "./greeter";
export class Loud extends Greeter implements Shape {
  greet(n: string): string { return this.greet(n) + super.greet(n) + ns.Greeter.make() + g.greet(n); }
}
function f(greet: number) {
  const s = "greet";
  const k = { greet: 1 };
  const sh = { greet };
  let q: Greeter = new Greeter();
  const t = function () { this.greet(); };
}
"""


@pytest.fixture
def parser() -> TypeScriptCodeStructure:
    return TypeScriptCodeStructure()


def _kinds(refs):  # type: ignore[no-untyped-def]
    return [(r.kind, r.line) for r in refs]


def test_a_method_name_in_every_role(parser: TypeScriptCodeStructure) -> None:
    refs = parser.find_references(_CODE, "greet")
    kinds = _kinds(refs)

    assert ("definition", 5) in kinds
    line5 = [r for r in refs if r.line == 5 and r.kind == "attribute"]
    assert [(r.receiver, r.receiver_binding) for r in line5] == [
        ("this", "this"),
        ("super", "super"),
        ("g", "free"),
    ]
    assert ("field", 7) in kinds
    assert ("string", 8) in kinds
    assert ("string", 9) in kinds
    assert ("string", 10) in kinds
    (rebound,) = [r for r in refs if r.line == 12]
    assert rebound.receiver_binding == "rebound"
    definition = next(r for r in refs if r.kind == "definition")
    assert (definition.scope, definition.owner) == ("class", "Loud")


def test_a_class_name_in_every_role(parser: TypeScriptCodeStructure) -> None:
    refs = parser.find_references(_CODE, "Greeter")
    kinds = _kinds(refs)

    assert ("import", 1) in kinds
    assert ("import", 3) in kinds
    assert ("bare", 4) in kinds
    assert ("attribute", 5) in kinds
    assert [k for k in kinds if k[1] == 11] == [("type", 11), ("bare", 11)]
    imports = [r for r in refs if r.kind == "import"]
    assert [(r.module, r.alias) for r in imports] == [("./greeter", None), ("./greeter", "G")]


def test_a_parameter_or_a_local_shadows(parser: TypeScriptCodeStructure) -> None:
    code = "function f(greet) { return greet; }\nfunction g() { const greet = 1; return greet; }\ngreet();\n"
    bare = [r for r in parser.find_references(code, "greet") if r.kind == "bare"]
    assert [r.binding for r in bare] == ["local", "local", "free"]


def test_spans_cover_exactly_the_name(parser: TypeScriptCodeStructure) -> None:
    for name in ("greet", "Greeter"):
        for r in parser.find_references(_CODE, name):
            if r.kind not in ("string", "text"):
                assert _CODE.encode()[r.start_byte : r.end_byte] == name.encode()


def test_file_bindings(parser: TypeScriptCodeStructure) -> None:
    code = (
        'import { A, B as C } from "./ab";\n'
        'import * as ns from "./ns";\n'
        'import D from "./d";\n'
        'export { E as F } from "./e";\n'
        'export * from "./all";\n'
        "export class K extends A implements ns.I {}\n"
        "export const fn = () => 1;\n"
        "let count = 0;\n"
        "export { fn as alias };\n"
    )
    facts = parser.file_bindings(code)

    assert facts.imports == {
        "A": ("./ab", "A"),
        "C": ("./ab", "B"),
        "ns": ("./ns", None),
        "D": ("./d", "default"),
    }
    assert facts.statics == {"F": ("./e", "E"), "alias": ("", "fn")}
    assert facts.wildcards == ["./all"]
    assert facts.defs == {"K", "fn"}
    assert facts.others == {"count"}
    assert facts.bases == {"K": ["A", "ns.I"]}


def test_an_abstract_class_and_its_abstract_method_are_symbols(
    parser: TypeScriptCodeStructure,
) -> None:
    code = "export abstract class A {\n  abstract go(): void;\n}\n"
    assert {"A", "A.go"} <= set(parser.list_symbols(code))
    kinds = _kinds(parser.find_references(code, "go"))
    assert kinds == [("definition", 2)]


def test_a_syntax_error_still_gives_references(parser: TypeScriptCodeStructure) -> None:
    refs = parser.find_references("function f( { greet(); }\nclass A { m() { greet(); } }", "greet")
    assert any(r.kind == "bare" for r in refs)


def test_comments_and_templates(parser: TypeScriptCodeStructure) -> None:
    refs = parser.find_references("// greet\nconst t = `say greet`;\n", "greet")
    assert _kinds(refs) == [("text", 1), ("text", 2)]
