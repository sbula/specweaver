# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A C or C++ rename planned across files: every proven use, or nothing.

Proves: D-SENS-06 FR-7
Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a C function with its header prototype and callers; a struct; a C++ method family |
| Boundary | a `static` function; a namespace; `using ns::f`; an out-of-line method |
| Degradation | a use with no declaration in reach; the name in a macro; `using namespace`; an outside base |
| Hostile | a local of the name; an unknown receiver; a keyword new name; two definitions of the name |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.cpp.codestructure import CppCodeStructure
from specweaver.workspace.ast.refactor.rename import RenamePlan, RenameRefusal, Spot, plan_rename

_C = CCodeStructure()
_CPP = CppCodeStructure()

_CPROJ = {
    "src/util.h": "#ifndef UTIL_H\n#define UTIL_H\nint total(int a);\nstruct Point { int x; };\n#endif\n",
    "src/util.c": '#include "util.h"\nint total(int a) { return a; }\n',
    "src/main.c": '#include "util.h"\nint main(void) { struct Point p; return total(p.x); }\n',
}

_CPPPROJ = {
    "src/greeter.hpp": (
        "namespace app {\n"
        "class Greeter {\n public:\n  int greet(int n);\n"
        "  int twice(int n) { return greet(n) + this->greet(n); }\n};\n"
        "class Loud : public Greeter {\n public:\n  int greet(int n) { return Greeter::greet(n) * 2; }\n};\n"
        "}\n"
    ),
    "src/greeter.cpp": '#include "greeter.hpp"\nnamespace app {\nint Greeter::greet(int n) { return n; }\n}\n',
}


def _plan(files: dict[str, str], path: str, symbol: str, new: str) -> RenamePlan:
    result = plan_rename(files, path, symbol, new, _C if path.endswith((".c", ".h")) else _CPP)
    assert isinstance(result, RenamePlan), result
    return result


def _refusal(files: dict[str, str], path: str, symbol: str, new: str) -> RenameRefusal:
    result = plan_rename(files, path, symbol, new, _C if path.endswith((".c", ".h")) else _CPP)
    assert isinstance(result, RenameRefusal), result
    return result


# --- Happy -----------------------------------------------------------------------------------


def test_a_c_function_with_its_prototype_and_callers() -> None:
    plan = _plan(_CPROJ, "src/util.c", "total", "sum")

    assert sorted(plan.changes) == ["src/main.c", "src/util.c", "src/util.h"]
    assert "int sum(int a);" in plan.changes["src/util.h"]
    assert "return sum(p.x);" in plan.changes["src/main.c"]


def test_a_c_struct_and_its_uses() -> None:
    plan = _plan(_CPROJ, "src/util.h", "Point", "Pos")
    assert "struct Pos { int x; };" in plan.changes["src/util.h"]
    assert "struct Pos p;" in plan.changes["src/main.c"]


def test_a_cpp_method_family_inline_out_of_line_and_qualified() -> None:
    plan = _plan(_CPPPROJ, "src/greeter.hpp", "Greeter.greet", "hello")

    header = plan.changes["src/greeter.hpp"]
    assert "  int hello(int n);" in header
    assert "return hello(n) + this->hello(n);" in header
    assert "int hello(int n) { return Greeter::hello(n) * 2; }" in header
    assert "int Greeter::hello(int n)" in plan.changes["src/greeter.cpp"]


# --- Boundary --------------------------------------------------------------------------------


def test_a_static_function_stays_in_its_file() -> None:
    files = {
        **_CPROJ,
        "src/a.c": "static int helper(int x) { return x; }\nint fa(void) { return helper(1); }\n",
        "src/b.c": "static int helper(int x) { return x * 2; }\nint fb(void) { return helper(2); }\n",
    }
    plan = _plan(files, "src/a.c", "helper", "assist")
    assert sorted(plan.changes) == ["src/a.c"]


def test_a_namespace_function_through_using() -> None:
    files = {
        "src/lib.hpp": "namespace lib {\nint run(int x);\n}\n",
        "src/lib.cpp": '#include "lib.hpp"\nnamespace lib {\nint run(int x) { return x; }\n}\n',
        "src/main.cpp": '#include "lib.hpp"\nusing lib::run;\nint main() { return run(1) + lib::run(2); }\n',
    }
    plan = _plan(files, "src/lib.cpp", "run", "go")
    assert (
        plan.changes["src/main.cpp"]
        == '#include "lib.hpp"\nusing lib::go;\nint main() { return go(1) + lib::go(2); }\n'
    )


# --- Degradation -----------------------------------------------------------------------------


def test_a_use_with_no_declaration_in_reach_is_unsure() -> None:
    files = {**_CPROJ, "src/other.c": "int f(void) { return total(3); }\n"}
    assert _refusal(files, "src/util.c", "total", "sum").spots == [Spot("src/other.c", 1)]


def test_the_name_in_a_macro_is_unsure() -> None:
    files = {**_CPROJ, "src/main.c": _CPROJ["src/main.c"] + "#define TWICE(x) (total(x) * 2)\n"}
    assert _refusal(files, "src/util.c", "total", "sum").spots == [Spot("src/main.c", 3)]


def test_using_namespace_is_unsure() -> None:
    files = {
        "src/lib.hpp": "namespace lib {\nint run(int x);\n}\n",
        "src/main.cpp": '#include "lib.hpp"\nusing namespace lib;\nint main() { return run(1); }\n',
    }
    assert _refusal(files, "src/lib.hpp", "run", "go").spots == [Spot("src/main.cpp", 3)]


def test_a_family_with_an_outside_base_refuses() -> None:
    files = {"src/w.hpp": "class W : public std::thread {\n public:\n  void go() {}\n};\n"}
    assert "outside the project" in _refusal(files, "src/w.hpp", "W.go", "run").reason


# --- Hostile ---------------------------------------------------------------------------------


def test_a_local_of_the_name_is_left_alone() -> None:
    files = {**_CPROJ, "src/main.c": _CPROJ["src/main.c"] + "int g(int total) { return total; }\n"}
    assert (
        "int g(int total) { return total; }"
        in _plan(files, "src/util.c", "total", "sum").changes["src/main.c"]
    )


def test_an_unknown_receiver_is_unsure() -> None:
    files = {
        **_CPPPROJ,
        "src/use.cpp": '#include "greeter.hpp"\nint f(app::Greeter* g) { return g->greet(1); }\n',
    }
    assert _refusal(files, "src/greeter.hpp", "Greeter.greet", "hello").spots == [
        Spot("src/use.cpp", 2)
    ]


@pytest.mark.parametrize("new", ["int", "return", "class", "1x"])
def test_a_keyword_new_name_refuses(new: str) -> None:
    assert _refusal(_CPROJ, "src/util.c", "total", new).reason


def test_two_external_definitions_refuse() -> None:
    files = {**_CPROJ, "src/again.c": "int total(int a) { return a + 1; }\n"}
    assert "several" in _refusal(files, "src/util.c", "total", "sum").reason
