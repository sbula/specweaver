# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place a name occurs in one Python file, and what it is there.

Proves: D-SENS-06 FR-2

The finder judges one file only: which scope binds a bare name, which object an attribute hangs
on, whether a string or a comment holds the name. Which of them are uses of a symbol is decided
across files by `workspace/ast/refactor`.

| Bucket | Case |
|---|---|
| Happy | definition, import, bare use, attribute with its receiver |
| Boundary | a local shadows the name; a class body binds it; an alias import; a keyword argument |
| Degradation | a file with a syntax error still gives its references |
| Hostile | the name in a string, in `global`, as `getattr` text |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure


@pytest.fixture
def parser() -> PythonCodeStructure:
    return PythonCodeStructure()


def _kinds(refs) -> list[tuple[str, int]]:  # type: ignore[no-untyped-def]
    return [(r.kind, r.line) for r in refs]


def test_definition_import_bare_and_attribute(parser: PythonCodeStructure) -> None:
    code = (
        "from app.greeter import greet\n"  # 1
        "class Greeter:\n"  # 2
        "    def greet(self):\n"  # 3
        "        return self.greet()\n"  # 4
        "def main():\n"  # 5
        "    greet()\n"  # 6
    )
    refs = parser.find_references(code, "greet")

    assert _kinds(refs) == [
        ("import", 1),
        ("definition", 3),
        ("attribute", 4),
        ("bare", 6),
    ]
    imp, definition, attr, bare = refs
    assert imp.module == "app.greeter"
    assert code.encode()[imp.start_byte : imp.end_byte] == b"greet"
    assert definition.owner == "Greeter"
    assert definition.scope == "class"
    assert attr.receiver == "self"
    assert attr.owner == "Greeter"
    assert bare.binding == "import"


def test_spans_cover_exactly_the_name(parser: PythonCodeStructure) -> None:
    code = "x = Greeter.greet(Greeter())\n"
    for ref in parser.find_references(code, "Greeter"):
        assert code.encode()[ref.start_byte : ref.end_byte] == b"Greeter"


def test_a_local_binding_shadows_the_name(parser: PythonCodeStructure) -> None:
    code = "def greet():\n    pass\ndef f(greet):\n    return greet\ndef g():\n    return greet\n"
    bare = [r for r in parser.find_references(code, "greet") if r.kind == "bare"]

    assert [(r.line, r.binding) for r in bare] == [(3, "local"), (4, "local"), (6, "module_def")]


@pytest.mark.parametrize(
    ("code", "line"),
    [
        ("def f():\n    greet = 1\n    return greet\n", 3),
        ("def f():\n    for greet in x:\n        pass\n    return greet\n", 4),
        ("def f():\n    with o() as greet:\n        return greet\n", 3),
        ("def f():\n    try:\n        pass\n    except E as greet:\n        return greet\n", 5),
        ("def f():\n    (greet := 1)\n    return greet\n", 3),
        ("def f():\n    import greet\n    return greet\n", 3),
        ("def f():\n    def greet():\n        pass\n    return greet\n", 4),
        ("f = lambda greet: greet\n", 1),
        ("def f(*greet):\n    return greet\n", 2),
        ("def f(greet: int = 1):\n    return greet\n", 2),
    ],
)
def test_every_kind_of_local_binding(parser: PythonCodeStructure, code: str, line: int) -> None:
    uses = [r for r in parser.find_references(code, "greet") if r.kind == "bare" and r.line == line]
    assert uses
    assert all(r.binding == "local" for r in uses), uses


def test_module_level_bindings(parser: PythonCodeStructure) -> None:
    def binding(code: str) -> str:
        return [r for r in parser.find_references(code, "greet") if r.kind == "bare"][-1].binding

    assert binding("x = greet\n") == "free"
    assert binding("greet = 1\nx = greet\n") == "module_other"
    assert binding("import greet\nx = greet\n") == "import"
    assert binding("def greet(): pass\ngreet = 2\nx = greet\n") == "mixed"


def test_a_class_body_binding_is_not_seen_by_its_methods(parser: PythonCodeStructure) -> None:
    code = (
        "def greet(): pass\n"
        "class A:\n"
        "    def greet(self): pass\n"
        "    alias = greet\n"  # 4: the class body sees its own greet
        "    def other(self):\n"
        "        return greet()\n"  # 6: a method sees the module's greet
    )
    bare = {r.line: r for r in parser.find_references(code, "greet") if r.kind == "bare"}

    assert bare[4].binding == "class"
    assert bare[4].owner == "A"
    assert bare[6].binding == "module_def"


def test_an_alias_import_records_its_alias(parser: PythonCodeStructure) -> None:
    code = "from .greeter import Greeter as G, other\n"
    (imp,) = parser.find_references(code, "Greeter")

    assert imp.kind == "import"
    assert imp.module == ".greeter"
    assert imp.alias == "G"


def test_a_keyword_argument_name_is_its_own_kind(parser: PythonCodeStructure) -> None:
    assert _kinds(parser.find_references("f(greet=1)\n", "greet")) == [("keyword", 1)]


def test_a_dotted_receiver_keeps_its_text(parser: PythonCodeStructure) -> None:
    (attr,) = [
        r
        for r in parser.find_references("import app\napp.greeter.greet()\n", "greet")
        if r.kind == "attribute"
    ]
    assert attr.receiver == "app.greeter"
    assert attr.receiver_binding == "import"


def test_strings_and_comments(parser: PythonCodeStructure) -> None:
    code = (
        'getattr(g, "greet")\n'  # 1: the whole string is the name
        '"""Say greet to all."""\n'  # 2: a word in a text
        "# greet here\n"  # 3
        'x = "greeting"\n'  # 4: not the word
    )
    assert _kinds(parser.find_references(code, "greet")) == [
        ("string", 1),
        ("text", 2),
        ("text", 3),
    ]


def test_global_and_nonlocal_escape_the_scope(parser: PythonCodeStructure) -> None:
    code = "def f():\n    global greet\n    greet = 1\n"
    refs = parser.find_references(code, "greet")

    assert ("scope_escape", 2) in _kinds(refs)
    assert all(r.binding != "local" for r in refs if r.kind == "bare")


def test_a_file_with_a_syntax_error_still_gives_references(parser: PythonCodeStructure) -> None:
    refs = parser.find_references("def f(:\n    pass\ngreet()\n", "greet")
    assert ("bare", 3) in _kinds(refs)


def test_an_empty_name_finds_nothing(parser: PythonCodeStructure) -> None:
    assert parser.find_references("x = 1\n", "") == []


def test_file_bindings(parser: PythonCodeStructure) -> None:
    code = (
        "import os\n"
        "import app.billing as bill\n"
        "from .greeter import Greeter as G\n"
        "from app import greeter\n"
        "from x import *\n"
        "def run(): pass\n"
        "class Loud(G, mod.Base, Generic[T], metaclass=M): pass\n"
        "count = 0\n"
    )
    facts = parser.file_bindings(code)

    assert facts.imports == {
        "os": ("os", None),
        "bill": ("app.billing", None),
        "G": (".greeter", "Greeter"),
        "greeter": ("app", "greeter"),
    }
    assert facts.wildcards == ["x"]
    assert facts.defs == {"run", "Loud"}
    assert facts.others == {"count"}
    assert facts.bases == {"Loud": ["G", "mod.Base", "Generic"]}


def test_find_references_is_only_offered_by_python() -> None:
    from specweaver.workspace.ast.parsers.factory import get_default_parsers
    from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

    for exts, other in get_default_parsers().items():
        if ".py" in exts:
            assert "rename" in other.supported_intents()
            continue
        assert "rename" not in other.supported_intents(), exts
        with pytest.raises(CodeStructureError):
            other.find_references("x", "x")
