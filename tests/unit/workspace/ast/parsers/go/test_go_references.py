# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place a name occurs in one Go file, and what it is there.

Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a function, a method with its receiver, a call through the receiver and an import |
| Boundary | an alias import, a dot import, an interface method |
| Degradation | a file with a syntax error still gives references |
| Hostile | a local of the name; the name as a string |
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure

_CODE = """package app

import (
\tu "example.com/m/util"
\t. "example.com/m/dot"
)

type Hello interface{ Greet() string }

func (g *Greeter) Greet() string { return g.Greet() + u.Greet() + x.Greet() }

func f() { Greet := 1; _ = Greet; s := "Greet" }
"""


def test_a_method_name_in_every_role() -> None:
    refs = GoCodeStructure().find_references(_CODE, "Greet")
    kinds = [(r.kind, r.line, r.binding or r.receiver_binding) for r in refs]

    assert ("definition", 8, "interface") in kinds
    method = next(r for r in refs if r.line == 10 and r.kind == "definition")
    assert (method.owner, method.alias) == ("Greeter", "g")
    assert [r.receiver_binding for r in refs if r.line == 10 and r.kind == "attribute"] == [
        "receiver",
        "import",
        "free",
    ]
    assert [(r.kind, r.binding) for r in refs if r.line == 12] == [
        ("field", None),
        ("bare", "local"),
        ("string", None),
    ]


def test_file_bindings() -> None:
    facts = GoCodeStructure().file_bindings(_CODE)
    assert facts.package == "app"
    assert facts.imports == {"u": ("example.com/m/util", "alias")}
    assert facts.wildcards == ["example.com/m/dot"]
    assert {"Hello", "f"} <= facts.defs


def test_a_syntax_error_still_gives_references() -> None:
    refs = GoCodeStructure().find_references(
        "package a\nfunc f( { Greet() }\nfunc g() { Greet() }\n", "Greet"
    )
    assert any(r.kind == "bare" for r in refs)
