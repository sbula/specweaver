# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place a name occurs in one C or C++ file, and what it is there.

Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a prototype, a definition, a call; a method inline, out of line and through `this` |
| Boundary | a `static` function; a namespace; a `using` declaration |
| Degradation | a file with a syntax error still gives references |
| Hostile | the name in a macro body; a parameter of the name |
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.cpp.codestructure import CppCodeStructure


def _kinds(refs):  # type: ignore[no-untyped-def]
    return [(r.kind, r.line) for r in refs]


def test_c_roles() -> None:
    code = (
        '#include "u.h"\n'
        "#define TWICE(x) (total(x) * 2)\n"
        "int total(int a);\n"
        "static int total2(int total) { return total; }\n"
        "int total(int a) { return a + total(a); }\n"
    )
    refs = CCodeStructure().find_references(code, "total")

    assert _kinds(refs) == [
        ("string", 2),
        ("declaration", 3),
        ("bare", 4),
        ("bare", 4),
        ("definition", 5),
        ("bare", 5),
    ]
    assert [r.binding for r in refs if r.line == 4] == ["local", "local"]
    static = CCodeStructure().find_references(code, "total2")[0]
    assert static.binding == "static"


def test_cpp_roles() -> None:
    code = (
        "namespace app {\nclass G {\n public:\n  int greet(int n);\n"
        "  int twice(int n) { return greet(n) + this->greet(n); }\n};\n"
        "int G::greet(int n) { return n; }\n}\n"
        "using app::G;\n"
    )
    refs = CppCodeStructure().find_references(code, "greet")
    assert [(r.kind, r.owner) for r in refs] == [
        ("declaration", "G"),
        ("bare", "G"),
        ("attribute", "G"),
        ("definition", "G"),
    ]
    assert refs[0].module == "app"
    (using,) = [r for r in CppCodeStructure().find_references(code, "G") if r.kind == "import"]
    assert using.qualifier == "app"


def test_file_bindings() -> None:
    facts = CppCodeStructure().file_bindings(
        '#include "u.hpp"\n#include <vector>\nusing namespace std;\nclass L : public G {};\n'
    )
    assert facts.imports == {"u.hpp": ("include", None)}
    assert facts.wildcards == ["std"]
    assert facts.bases == {"L": ["G"]}
    assert "L" in facts.defs


def test_a_syntax_error_still_gives_references() -> None:
    refs = CCodeStructure().find_references(
        "int f( { total(); }\nint g(void) { return total(); }\n", "total"
    )
    assert any(r.kind == "bare" for r in refs)
