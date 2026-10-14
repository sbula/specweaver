# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Go rename planned across a module's packages: every proven use, or nothing.

Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a function in its package and through an import; a type; a method through its receiver |
| Boundary | an import alias; a package named unlike its folder; a `_test` package; a method expression |
| Degradation | a dot import; an interface declaring the method; a standard method name |
| Hostile | an exported name made unexported; an unknown receiver; a local of the name; a string |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.refactor.rename import RenamePlan, RenameRefusal, Spot, plan_rename

_GO = GoCodeStructure()

_MODULE = {
    "go.mod": "module example.com/m\n\ngo 1.22\n",
    "util/util.go": (
        "package util\n\n"
        "type Greeter struct{ name string }\n\n"
        "func (g *Greeter) Greet() string { return g.name + g.Greet() }\n\n"
        "func Total(a int) int { return a }\n"
    ),
    "util/more.go": "package util\n\nfunc twice(a int) int { return Total(a) + Total(a) }\n",
    "app/main.go": (
        "package main\n\n"
        'import (\n\t"fmt"\n\tu "example.com/m/util"\n)\n\n'
        "func main() {\n\tg := &u.Greeter{}\n\tfmt.Println(u.Total(1), g)\n}\n"
    ),
}


def _plan(files: dict[str, str], path: str, symbol: str, new: str) -> RenamePlan:
    result = plan_rename(files, path, symbol, new, _GO)
    assert isinstance(result, RenamePlan), result
    return result


def _refusal(files: dict[str, str], path: str, symbol: str, new: str) -> RenameRefusal:
    result = plan_rename(files, path, symbol, new, _GO)
    assert isinstance(result, RenameRefusal), result
    return result


# --- Happy -----------------------------------------------------------------------------------


def test_a_function_in_its_package_and_through_an_import() -> None:
    plan = _plan(_MODULE, "util/util.go", "Total", "Sum")

    assert "func Sum(a int) int" in plan.changes["util/util.go"]
    assert "return Sum(a) + Sum(a)" in plan.changes["util/more.go"]
    assert "u.Sum(1)" in plan.changes["app/main.go"]


def test_a_type_through_an_import() -> None:
    plan = _plan(_MODULE, "util/util.go", "Greeter", "Welcomer")

    assert "type Welcomer struct" in plan.changes["util/util.go"]
    assert "func (g *Welcomer) Greet()" in plan.changes["util/util.go"]
    assert "g := &u.Welcomer{}" in plan.changes["app/main.go"]


def test_a_method_through_its_receiver() -> None:
    plan = _plan(_MODULE, "util/util.go", "Greeter.Greet", "Hello")
    assert (
        "func (g *Greeter) Hello() string { return g.name + g.Hello() }"
        in plan.changes["util/util.go"]
    )


# --- Boundary --------------------------------------------------------------------------------


def test_a_package_named_unlike_its_folder() -> None:
    files = {
        **_MODULE,
        "lib/v2/lib.go": "package lib\n\nfunc Run() {}\n",
        "app/run.go": 'package main\n\nimport "example.com/m/lib/v2"\n\nfunc r() { lib.Run() }\n',
    }
    assert "lib.Go()" in _plan(files, "lib/v2/lib.go", "Run", "Go").changes["app/run.go"]


def test_an_external_test_package_uses_the_import() -> None:
    files = {
        **_MODULE,
        "util/util_test.go": 'package util_test\n\nimport "example.com/m/util"\n\nfunc t() { util.Total(1) }\n',
    }
    assert (
        "util.Sum(1)" in _plan(files, "util/util.go", "Total", "Sum").changes["util/util_test.go"]
    )


def test_a_method_expression_is_renamed() -> None:
    files = {**_MODULE, "util/more.go": _MODULE["util/more.go"] + "\nvar f = (*Greeter).Greet\n"}
    assert (
        "(*Greeter).Hello"
        in _plan(files, "util/util.go", "Greeter.Greet", "Hello").changes["util/more.go"]
    )


def test_a_same_named_function_in_another_package_is_left_alone() -> None:
    files = {**_MODULE, "other/o.go": "package other\n\nfunc Total() int { return Total() }\n"}
    assert "other/o.go" not in _plan(files, "util/util.go", "Total", "Sum").changes


# --- Degradation -----------------------------------------------------------------------------


def test_a_dot_import_is_unsure() -> None:
    files = {
        **_MODULE,
        "app/dot.go": 'package main\n\nimport . "example.com/m/util"\n\nvar x = Total(1)\n',
    }
    assert _refusal(files, "util/util.go", "Total", "Sum").spots == [Spot("app/dot.go", 5)]


def test_a_method_an_interface_declares_refuses() -> None:
    files = {**_MODULE, "util/iface.go": "package util\n\ntype Hi interface{ Greet() string }\n"}
    assert "interface" in _refusal(files, "util/util.go", "Greeter.Greet", "Hello").reason


@pytest.mark.parametrize("name", ["String", "Error", "Close"])
def test_a_standard_method_name_refuses(name: str) -> None:
    files = {
        "go.mod": "module example.com/m\n",
        "a/a.go": f'package a\n\ntype T struct{{}}\n\nfunc (t T) {name}() string {{ return "" }}\n',
    }
    assert "standard" in _refusal(files, "a/a.go", f"T.{name}", "Show").reason


# --- Hostile ---------------------------------------------------------------------------------


def test_making_an_exported_name_unexported_refuses() -> None:
    assert "exported" in _refusal(_MODULE, "util/util.go", "Total", "sum").reason


def test_a_local_receiver_variable_is_unsure() -> None:
    files = {
        **_MODULE,
        "util/more.go": _MODULE["util/more.go"]
        + "\nfunc z(v *Greeter) string { return v.Greet() }\n",
    }
    assert _refusal(files, "util/util.go", "Greeter.Greet", "Hello").spots == [
        Spot("util/more.go", 5)
    ]


def test_a_local_of_the_name_is_left_alone() -> None:
    files = {
        **_MODULE,
        "util/more.go": _MODULE["util/more.go"] + "\nfunc k() int { Total := 1; return Total }\n",
    }
    assert (
        "Total := 1; return Total }"
        in _plan(files, "util/util.go", "Total", "Sum").changes["util/more.go"]
    )


def test_the_name_as_a_string_is_unsure() -> None:
    files = {**_MODULE, "util/more.go": _MODULE["util/more.go"] + '\nvar n = "Total"\n'}
    assert _refusal(files, "util/util.go", "Total", "Sum").spots == [Spot("util/more.go", 5)]
