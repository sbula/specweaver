# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What every parser reports today, captured before SF-01 changes any of it.

Proves: B-SENS-03 NFR-5

**These tests are green on their first run, and that is their job.** `NFR-5` is a *must-not-change*
requirement, and the only way to prove something did not change is to capture it before and compare
after. A test written to go red would be testing a different claim.

That makes the usual protection unavailable, so this file's validity rests on **probes** instead
(`B-SENS-03_sf01_implementation_plan.md`, CB-1 T3): the filter is neutralised in each of the five
places one lives, and this file must object every time. A probe nothing kills means the net has a
hole over that parser. `_reading.py` alone covers only four of the ten — C, C++, Go and Python each
carry their own filter, which is where three of the known defects sit.

Every literal below was **measured on 2026-08-26**, not reasoned out. Several are wrong, and they
are pinned as-is on purpose: a net that quietly corrects what it is measuring cannot show a diff.
Each known-wrong value carries the reason beside it.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers

_BY_CLASS = {
    "CCodeStructure": "c",
    "CppCodeStructure": "cpp",
    "PythonCodeStructure": "python",
    "JavaCodeStructure": "java",
    "TypeScriptCodeStructure": "typescript",
    "RustCodeStructure": "rust",
    "KotlinCodeStructure": "kotlin",
    "MarkdownCodeStructure": "markdown",
    "GoCodeStructure": "go",
    "SqlCodeStructure": "sql",
}


@pytest.fixture(scope="module")
def parsers() -> dict[str, typing.Any]:
    """Every shipped parser, keyed by language.

    Built from `get_default_parsers()` rather than a hand-written list, so a language added to the
    registry and forgotten here fails `test_every_shipped_parser_is_covered` instead of being
    silently uncovered.
    """
    found = {}
    for parser in get_default_parsers().values():
        found[_BY_CLASS[type(parser).__name__]] = parser
    return found


#: One fixture per language, each deliberately containing the shapes SF-01 predicts a delta for:
#: a Python dunder beside a name-mangled member, a Java interface, a Rust trait with both a
#: required and a defaulted method, a TypeScript exported class with private and protected members,
#: a lowercase Go identifier, a C `static`, C++ class-versus-struct defaults, a qualified SQL name.
FIXTURES: dict[str, str] = {
    "python": '''"""Module doc."""
import os

CONSTANT = 1

class Store:
    """Doc."""
    def __init__(self, x): self.x = x
    def __repr__(self): return "Store"
    def get(self): return self.x
    def _helper(self): return 1
    def __mangled(self): return 2

def free(): return 3
def _private_free(): return 4
''',
    "java": """public interface Shape {
    double area();
    String name();
}
public class Circle implements Shape {
    private double r;
    public double area() { return r; }
    protected void log() {}
    void packagePrivate() {}
    private double helper() { return 1; }
    public String name() { return "c"; }
}
""",
    "kotlin": """interface Shape {
    fun area(): Double
}
class Circle : Shape {
    override fun area() = 1.0
    protected fun log() {}
    internal fun mod() {}
    private fun helper() = 1
}
fun free() = 2
""",
    "typescript": """export interface Shape { area(): number }
export class Circle {
    public area(): number { return 1 }
    protected log(): void {}
    private helper(): number { return 2 }
}
class Hidden { run(): void {} }
export function free(): number { return 3 }
function notExported(): number { return 4 }
""",
    "rust": """pub trait Shape {
    fn area(&self) -> f64;
    fn name(&self) -> f64 { 1.0 }
}
pub struct Circle;
impl Circle {
    pub fn area(&self) -> f64 { 1.0 }
    pub(crate) fn crate_only(&self) -> f64 { 2.0 }
    fn helper(&self) -> f64 { 3.0 }
}
pub fn free() -> f64 { 4.0 }
fn private_free() -> f64 { 5.0 }
""",
    "go": """package shapes

type Circle struct{}

func (c Circle) Area() float64 { return 1.0 }
func (c Circle) helper() float64 { return 2.0 }
func Free() float64 { return 3.0 }
func notExported() float64 { return 4.0 }
""",
    "c": """struct Point { int x; int y; };
enum Colour { RED, GREEN };
static int helper(int a) { return a; }
int public_fn(int a) { return a; }
""",
    "cpp": """class Widget {
    int hidden_by_default;
public:
    int visible() { return 1; }
protected:
    int guarded() { return 2; }
private:
    int secret() { return 3; }
};
struct Plain {
    int open() { return 4; }
};
int free_fn() { return 5; }
""",
    "sql": """CREATE TABLE public.orders (id INT);
CREATE VIEW summary AS SELECT 1;
CREATE FUNCTION analytics.total() RETURNS INT AS $$ SELECT 1 $$ LANGUAGE SQL;
""",
    "markdown": """# Title

Text.

## Section

More.

### Deep

End.
""",
}

_PY_ALL = [
    "Store",
    "Store.__init__",
    "Store.__repr__",
    "Store.get",
    "Store._helper",
    "Store.__mangled",
    "free",
    "_private_free",
]
_JAVA_ALL = [
    "Shape",
    "Shape.area",
    "Shape.name",
    "Circle",
    "Circle.area",
    "Circle.log",
    "Circle.packagePrivate",
    "Circle.helper",
    "Circle.name",
]
_KT_ALL = [
    "Shape",
    "Shape.area",
    "Circle",
    "Circle.area",
    "Circle.log",
    "Circle.mod",
    "Circle.helper",
    "free",
]
_TS_ALL = [
    "Circle",
    "Circle.area",
    "Circle.log",
    "Circle.helper",
    "Hidden",
    "Hidden.run",
    "free",
    "notExported",
]
_RS_ALL = [
    "Shape",
    "name",
    "Circle",
    "Circle.area",
    "Circle.crate_only",
    "Circle.helper",
    "free",
    "private_free",
]
_GO_ALL = ["Circle", "Circle.Area", "Circle.helper", "Free", "notExported"]
_C_ALL = ["Point", "Colour", "helper", "public_fn"]
_CPP_ALL = [
    "Widget",
    "Widget.visible",
    "Widget.guarded",
    "Widget.secret",
    "Plain",
    "Plain.open",
    "free_fn",
]
#: `public.orders` and `analytics.total` were each reported as TWO symbols until 2026-08-26
#: `[agreed 2026-08-26]`: the capture sat on `identifier`, and an `object_reference` holds one
#: per name part. The index carried a chunk literally named `public`.
_SQL_ALL = ["public.orders", "summary", "analytics.total"]
_MD_ALL = ["Title", "Title.Section", "Title.Section.Deep"]

#: `list_symbols(code)` with no filter — every name each parser can see.
UNFILTERED: dict[str, list[str]] = {
    "python": _PY_ALL,
    "java": _JAVA_ALL,
    "kotlin": _KT_ALL,
    # `Shape.area` — the trait's REQUIRED method — is absent, and the defaulted `name` arrives with
    # no scope where `Shape.name` is expected. Two lost names, pinned as-is: SF-03 `FR-18` owns them.
    "rust": _RS_ALL,
    # `Shape` (the interface) is missing entirely: TypeScript interfaces are never reported.
    # Parked with the graph classifier by decision on 2026-08-26.
    "typescript": _TS_ALL,
    "go": _GO_ALL,
    "c": _C_ALL,
    "cpp": _CPP_ALL,
    # `public.orders` and `analytics.total` each arrive as TWO symbols. SF-03 `FR-7` owns this.
    "sql": _SQL_ALL,
    "markdown": _MD_ALL,
}

#: `visibility=["public"]`. This is the set `extract_public_symbols` feeds into the generated
#: `context.yaml` `exposes:` list, which is why four of its entries went to the user as decisions.
PUBLIC_ONLY: dict[str, list[str]] = {
    # `Store.__mangled` LEFT on 2026-08-26 `[agreed 2026-08-26]`. It was here — name-mangled, and
    # in the list that writes `exposes:`. `__init__` and `__repr__` stay: dunders are interface.
    "python": ["Store", "Store.__init__", "Store.__repr__", "Store.get", "free"],
    # `Shape.area` and `Shape.name` JOINED `[agreed 2026-08-26]`. Both are implicitly public by
    # JLS; the old filter read "no modifier" as hidden, which is right for a class only.
    "java": ["Shape", "Shape.area", "Shape.name", "Circle", "Circle.area", "Circle.name"],
    "kotlin": ["Shape", "Shape.area", "Circle", "Circle.area", "free"],
    # `Circle.log` (protected) and `Circle.helper` (private) LEFT. TypeScript now reads a member's
    # accessibility instead of only asking whether an ancestor is exported (`FR-3`).
    "typescript": ["Circle", "Circle.area", "free"],
    # `name` — the trait's defaulted method — JOINED `[agreed 2026-08-26]`, same rule as Java's.
    # `Circle.crate_only` LEFT: `pub(crate)` is `internal`, so a request for `public` excludes it.
    # That one follows from `FR-1`'s vocabulary rather than being a separate decision.
    "rust": ["Shape", "name", "Circle", "Circle.area", "free"],
    "go": ["Circle", "Circle.Area", "Free"],
    # WAS EMPTY for every request `[agreed 2026-08-26]`. C reports `unknown`, and `unknown` counts
    # as visible, so a request for the visible set now gets an answer instead of silence.
    "c": _C_ALL,
    "cpp": ["Widget", "Widget.visible", "Plain", "Plain.open", "free_fn"],
    "sql": _SQL_ALL,
    "markdown": _MD_ALL,
}

#: Where the fail-open used to be recorded.
#:
#: This file once carried `FAILS_OPEN_TO` and a class asserting that a request for `protected`,
#: `private` or a nonsense word returned the WHOLE FILE on nine of ten parsers. That was the defect
#: `FR-2` closed on 2026-08-26. It is deleted rather than inverted here: a net exists to make one
#: change readable, and keeping a defect pinned after it is fixed turns the record into a claim.
#:
#: The positive form — a request returns exactly the level asked for — lives in
#: `test_visibility_filter.py`, where it is the requirement rather than the archaeology.


class TestListSymbolsCoversEveryParser:
    def test_every_shipped_parser_is_covered(self, parsers: dict[str, typing.Any]) -> None:
        """A language added to the registry must not slip past this net unnoticed."""
        assert set(parsers) == set(FIXTURES) == set(UNFILTERED) == set(PUBLIC_ONLY)


@pytest.mark.parametrize("lang", sorted(FIXTURES), ids=str)
class TestListSymbolsTodaysAnswers:
    """[Happy path] The two sets that matter, per language, as literals measured on 2026-08-26."""

    def test_unfiltered_listing(self, parsers: dict[str, typing.Any], lang: str) -> None:
        assert parsers[lang].list_symbols(FIXTURES[lang]) == UNFILTERED[lang]

    def test_public_only_listing(self, parsers: dict[str, typing.Any], lang: str) -> None:
        assert (
            parsers[lang].list_symbols(FIXTURES[lang], visibility=["public"]) == PUBLIC_ONLY[lang]
        )


class TestListSymbolsOnCppFiltersProperly:
    """[Happy path] C++ is the reference: it filters on a real access level and fails CLOSED.

    `cpp/codestructure.py:133` already carries `_get_symbol_visibility(name_node) -> str`. SF-01
    promotes that shape to the base, so this class is the contract the other nine grow into — and
    it must not regress on the way.
    """

    def test_protected_returns_only_the_protected_member(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        assert parsers["cpp"].list_symbols(FIXTURES["cpp"], visibility=["protected"]) == [
            "Widget.guarded"
        ]

    def test_private_returns_only_the_private_member(self, parsers: dict[str, typing.Any]) -> None:
        assert parsers["cpp"].list_symbols(FIXTURES["cpp"], visibility=["private"]) == [
            "Widget.secret"
        ]

    def test_a_nonsense_level_returns_nothing(self, parsers: dict[str, typing.Any]) -> None:
        assert parsers["cpp"].list_symbols(FIXTURES["cpp"], visibility=["nonsense"]) == []

    def test_a_class_defaults_to_private_and_a_struct_to_public(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        public = parsers["cpp"].list_symbols(FIXTURES["cpp"], visibility=["public"])
        assert "Plain.open" in public
        assert "Widget.secret" not in public


@pytest.mark.parametrize("lang", sorted(FIXTURES), ids=str)
class TestListSymbolsEdgesAndHostileInput:
    def test_an_empty_file_yields_no_symbols(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] Nothing in, nothing out — for every language."""
        assert parsers[lang].list_symbols("") == []

    def test_whitespace_only_yields_no_symbols(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] The early return is on `code.strip()`, not on `code`."""
        assert parsers[lang].list_symbols("   \n\t\n  ") == []

    def test_an_empty_visibility_list_filters_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] `[]` means *no filter*, and now means it everywhere.

        Three answers came from this one input before 2026-08-26: eight parsers read it as falsy
        and returned everything, while C asked `visibility is None` and C++ tested membership, so
        both returned nothing. One shared filter is what removed the disagreement.
        """
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=[]) == UNFILTERED[lang]

    def test_unparseable_source_degrades_without_raising(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Graceful degradation] tree-sitter is error-tolerant, so nonsense yields few or no
        symbols rather than an exception. A parser that raises here would take a whole scan down."""
        symbols = parsers[lang].list_symbols("<<<< not %% any known ~~~ language >>>>")
        assert isinstance(symbols, list)
