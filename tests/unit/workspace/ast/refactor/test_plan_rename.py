# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Python rename planned across files: every proven use changes, or nothing does.

Proves: D-SENS-06 FR-1
Proves: D-SENS-06 FR-2
Proves: D-SENS-06 FR-3
Proves: D-SENS-06 FR-5

| Bucket | Case |
|---|---|
| Happy | a function, a class and a method renamed with their imports, calls and re-exports |
| Boundary | an alias import, a shadowing local, a `src/` layout, the 50-spot cap, sorted output |
| Degradation | a constant, an overload, an override, an outside base, a dunder, a missing module |
| Hostile | a keyword or taken new name, `getattr` text, an unknown receiver, `global`, a free name |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.refactor.rename import (
    RenamePlan,
    RenameRefusal,
    Spot,
    listing,
    plan_rename,
)

_PARSER = PythonCodeStructure()

_BILLING = {
    "app/__init__.py": "",
    "app/billing.py": "def total(a, b):\n    return a + b\n",
    "app/main.py": "from app.billing import total\n\nprint(total(1, 2))\n",
    "app/report.py": "import app.billing as bill\n\nx = bill.total(1, 2)\n",
}

_GREETER = {
    "app/__init__.py": "from .greeter import Greeter\n",
    "app/greeter.py": (
        "class Greeter:\n"
        "    def greet(self, name):\n"
        "        return 'Hello ' + name\n"
        "\n"
        "    def twice(self, name):\n"
        "        return self.greet(name) + self.greet(name)\n"
    ),
    "app/loud.py": (
        "from app.greeter import Greeter\n"
        "\n"
        "class Loud(Greeter):\n"
        "    def shout(self, name):\n"
        "        return self.greet(name).upper()\n"
    ),
    "app/use.py": "from app import Greeter\n\nprint(Greeter.greet(Greeter(), 'x'))\n",
    "app/other.py": "class Other:\n    def greet(self):\n        return self.greet\n",
}


def _plan(files: dict[str, str], path: str, symbol: str, new: str) -> RenamePlan:
    result = plan_rename(files, path, symbol, new, _PARSER)
    assert isinstance(result, RenamePlan), result
    return result


def _refusal(files: dict[str, str], path: str, symbol: str, new: str) -> RenameRefusal:
    result = plan_rename(files, path, symbol, new, _PARSER)
    assert isinstance(result, RenameRefusal), result
    return result


# --- Happy -----------------------------------------------------------------------------------


def test_a_function_and_every_use_of_it() -> None:
    plan = _plan(_BILLING, "app/billing.py", "total", "sum_up")

    assert plan.changes == {
        "app/billing.py": "def sum_up(a, b):\n    return a + b\n",
        "app/main.py": "from app.billing import sum_up\n\nprint(sum_up(1, 2))\n",
        "app/report.py": "import app.billing as bill\n\nx = bill.sum_up(1, 2)\n",
    }


def test_a_class_its_subclass_and_a_re_export() -> None:
    plan = _plan(_GREETER, "app/greeter.py", "Greeter", "Welcomer")

    assert sorted(plan.changes) == [
        "app/__init__.py",
        "app/greeter.py",
        "app/loud.py",
        "app/use.py",
    ]
    assert plan.changes["app/loud.py"].startswith(
        "from app.greeter import Welcomer\n\nclass Loud(Welcomer):"
    )
    assert plan.changes["app/use.py"] == (
        "from app import Welcomer\n\nprint(Welcomer.greet(Welcomer(), 'x'))\n"
    )


def test_a_method_its_self_calls_its_class_calls_and_its_subclass() -> None:
    plan = _plan(_GREETER, "app/greeter.py", "Greeter.greet", "welcome")

    assert sorted(plan.changes) == ["app/greeter.py", "app/loud.py", "app/use.py"]
    assert plan.changes["app/greeter.py"].count("welcome") == 3
    assert "self.welcome(name).upper()" in plan.changes["app/loud.py"]
    assert "Greeter.welcome(Greeter(), 'x')" in plan.changes["app/use.py"]


def test_a_bare_method_name_stands_for_its_one_class() -> None:
    plan = _plan(_GREETER, "app/greeter.py", "twice", "double")
    assert "def double(self, name)" in plan.changes["app/greeter.py"]


def test_text_mentions_are_reported_and_not_changed() -> None:
    files = {
        **_BILLING,
        "README.md": "# Billing\n\nCall total to add.\n",
        "app/billing.py": "# total adds\ndef total(a, b):\n    return a + b\n",
    }
    plan = _plan(files, "app/billing.py", "total", "sum_up")

    assert plan.mentions == [Spot("README.md", 3), Spot("app/billing.py", 1)]
    assert "README.md" not in plan.changes
    assert plan.changes["app/billing.py"].startswith("# total adds\ndef sum_up")


# --- Boundary --------------------------------------------------------------------------------


def test_an_alias_import_changes_only_the_imported_name() -> None:
    files = {**_BILLING, "app/main.py": "from app.billing import total as t\n\nprint(t(1, 2))\n"}
    plan = _plan(files, "app/billing.py", "total", "sum_up")
    assert plan.changes["app/main.py"] == "from app.billing import sum_up as t\n\nprint(t(1, 2))\n"


def test_a_local_of_the_same_name_elsewhere_is_left_alone() -> None:
    files = {**_BILLING, "app/calc.py": "def f(total):\n    return total * 2\n"}
    plan = _plan(files, "app/billing.py", "total", "sum_up")
    assert "app/calc.py" not in plan.changes


def test_a_relative_import_and_a_src_layout() -> None:
    files = {
        "src/app/__init__.py": "",
        "src/app/billing.py": "def total():\n    return 0\n",
        "src/app/main.py": "from .billing import total\nfrom app.billing import total as t\n",
    }
    plan = _plan(files, "src/app/billing.py", "total", "sum_up")
    assert plan.changes["src/app/main.py"] == (
        "from .billing import sum_up\nfrom app.billing import sum_up as t\n"
    )


def test_an_outside_module_with_the_same_name_is_left_alone() -> None:
    files = {**_BILLING, "app/x.py": "from os.path import join as total\nfrom m import total\n"}
    plan = _plan(files, "app/billing.py", "total", "sum_up")
    assert "app/x.py" not in plan.changes


def test_a_class_in_an_unrelated_hierarchy_keeps_its_method() -> None:
    plan = _plan(_GREETER, "app/greeter.py", "Greeter.greet", "welcome")
    assert "app/other.py" not in plan.changes


def test_changes_come_in_path_order() -> None:
    plan = _plan(_GREETER, "app/greeter.py", "Greeter", "Welcomer")
    assert list(plan.changes) == sorted(plan.changes)


def test_listing_names_50_spots_then_counts_the_rest() -> None:
    spots = [Spot("a.py", n) for n in range(1, 61)]
    text = listing(spots)

    assert "a.py:50" in text
    assert "a.py:51" not in text
    assert text.endswith("+10 more")
    assert listing(spots[:2]) == "a.py:1, a.py:2"


# --- Degradation -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("files", "symbol", "reason"),
    [
        ({"a.py": "COUNT = 0\n"}, "COUNT", "functions, methods and classes"),
        ({"a.py": "def f(): pass\n"}, "g", "functions, methods and classes"),
        (
            {
                "a.py": "class A:\n    @property\n    def x(self): ...\n    @x.setter\n    def x(self, v): ...\n"
            },
            "A.x",
            "defined more than once",
        ),
        ({"a.py": "class A:\n    def __init__(self): pass\n"}, "A.__init__", "special"),
        ({"a.py": "class A:\n    def run(self): pass\n"}, "A.run", "nothing"),
    ],
)
def test_a_symbol_that_cannot_be_renamed(files: dict[str, str], symbol: str, reason: str) -> None:
    new = "run" if symbol == "A.run" else "fresh"
    assert reason in _refusal(files, "a.py", symbol, new).reason


def test_an_override_refuses_until_the_override_family_lands() -> None:
    files = {
        **_GREETER,
        "app/loud.py": _GREETER["app/loud.py"] + "    def greet(self, n):\n        return n\n",
    }
    refusal = _refusal(files, "app/greeter.py", "Greeter.greet", "welcome")
    assert "override" in refusal.reason
    assert refusal.spots == [Spot("app/loud.py", 6)]


@pytest.mark.parametrize("base", ["Thread", "threading.Thread", "Unknown"])
def test_a_method_of_a_class_with_an_outside_base_refuses(base: str) -> None:
    files = {
        "a.py": f"import threading\nfrom threading import Thread\nclass A({base}):\n    def go(self): pass\n"
    }
    assert "base" in _refusal(files, "a.py", "A.go", "start").reason


@pytest.mark.parametrize("base", ["ABC", "Generic[T]", "object", "Protocol"])
def test_a_method_of_a_class_with_a_harmless_base_renames(base: str) -> None:
    files = {"a.py": f"class A({base}):\n    def go(self): pass\n"}
    assert "def start(self)" in _plan(files, "a.py", "A.go", "start").changes["a.py"]


def test_an_import_from_a_missing_project_module_is_unsure() -> None:
    files = {**_BILLING, "app/x.py": "from app.missing import total\n"}
    refusal = _refusal(files, "app/billing.py", "total", "sum_up")
    assert refusal.spots == [Spot("app/x.py", 1)]


def test_a_rename_that_breaks_parsing_refuses() -> None:
    class Broken(PythonCodeStructure):
        @property
        def parser(self):  # type: ignore[override]
            real = PythonCodeStructure().parser

            class _P:
                def parse(self, data: bytes):  # type: ignore[no-untyped-def]
                    tree = real.parse(data)
                    if b"sum_up" in data:
                        return real.parse(b"def (:\n")
                    return tree

            return _P()

    result = plan_rename(_BILLING, "app/billing.py", "total", "sum_up", Broken())
    assert isinstance(result, RenameRefusal)
    assert "parse" in result.reason


# --- Hostile ---------------------------------------------------------------------------------


@pytest.mark.parametrize("new", ["class", "match", "", "1abc", "a-b", "total"])
def test_a_new_name_that_is_not_a_free_identifier(new: str) -> None:
    assert _refusal(_BILLING, "app/billing.py", "total", new).reason


def test_a_new_name_already_used_in_a_changed_file() -> None:
    files = {
        **_BILLING,
        "app/main.py": "from app.billing import total\nsum_up = 1\nprint(total(1, 2))\n",
    }
    refusal = _refusal(files, "app/billing.py", "total", "sum_up")
    assert refusal.spots == [Spot("app/main.py", 2)]


def test_a_new_name_taken_by_a_sibling_method() -> None:
    refusal = _refusal(_GREETER, "app/greeter.py", "Greeter.greet", "twice")
    assert Spot("app/greeter.py", 5) in refusal.spots


@pytest.mark.parametrize(
    ("extra", "line"),
    [
        ('g = None\nprint(getattr(g, "total"))\n', 2),
        ("def f(o):\n    return o.total()\n", 2),
        ("def f():\n    global total\n    total = 1\n", 2),
        ("print(total(1, 2))\n", 1),
        ("from app.billing import *\nprint(total(1, 2))\n", 2),
        ("__all__ = ['total']\n", 1),
    ],
)
def test_an_unsure_use_refuses_and_names_the_spot(extra: str, line: int) -> None:
    files = {**_BILLING, "app/zz.py": extra}
    refusal = _refusal(files, "app/billing.py", "total", "sum_up")

    assert Spot("app/zz.py", line) in refusal.spots
    assert "unsure" in refusal.reason


def test_an_unknown_receiver_refuses_a_method_rename() -> None:
    files = {**_GREETER, "app/zz.py": "def f(g):\n    return g.greet('x')\n"}
    assert _refusal(files, "app/greeter.py", "Greeter.greet", "welcome").spots == [
        Spot("app/zz.py", 2)
    ]


def test_a_file_that_is_not_python_refuses() -> None:
    assert "Python" in _refusal({"a.ts": "function f() {}\n"}, "a.ts", "f", "g").reason


def test_a_path_that_is_not_in_the_project_refuses() -> None:
    assert _refusal(_BILLING, "../etc/x.py", "total", "sum_up").reason


def test_an_import_through_a_wildcard_module_is_unsure() -> None:
    files = {
        **_BILLING,
        "app/hub.py": "from app.other import *\n",
        "app/other.py": "",
        "app/zz.py": "from app.hub import total\n",
    }
    assert _refusal(files, "app/billing.py", "total", "sum_up").spots == [Spot("app/zz.py", 1)]


def test_a_local_that_shadows_the_class_name_is_unsure() -> None:
    files = {
        **_GREETER,
        "app/zz.py": "from app import Greeter\ndef f(Greeter):\n    return Greeter.greet(1)\n",
    }
    assert _refusal(files, "app/greeter.py", "Greeter.greet", "welcome").spots == [
        Spot("app/zz.py", 3)
    ]


def test_a_call_through_a_package_and_its_submodule() -> None:
    files = {
        **_BILLING,
        "app/zz.py": "import app.billing\nfrom . import billing\nx = app.billing.total(1, 2)\ny = billing.total(3, 4)\n",
    }
    plan = _plan(files, "app/billing.py", "total", "sum_up")
    assert plan.changes["app/zz.py"].count("sum_up") == 2


def test_a_relative_import_above_the_root_is_unsure() -> None:
    files = {**_BILLING, "app/zz.py": "from ...billing import total\n"}
    assert _refusal(files, "app/billing.py", "total", "sum_up").spots == [Spot("app/zz.py", 1)]


def test_a_re_export_cycle_is_unsure() -> None:
    files = {
        **_BILLING,
        "app/a.py": "from app.b import total\n",
        "app/b.py": "from app.a import total\n",
    }
    refusal = _refusal(files, "app/billing.py", "total", "sum_up")
    assert {s.path for s in refusal.spots} == {"app/a.py", "app/b.py"}


def test_a_name_both_defined_and_imported_is_unsure() -> None:
    files = {**_BILLING, "app/zz.py": "from app.billing import total\ndef total(): pass\ntotal()\n"}
    assert _refusal(files, "app/billing.py", "total", "sum_up").spots == [Spot("app/zz.py", 3)]
