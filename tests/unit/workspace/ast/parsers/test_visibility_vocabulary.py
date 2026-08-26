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
_SQL_ALL = ["public", "orders", "summary", "analytics", "total"]
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
    # `Store.__mangled` IS HERE. Name-mangled and in the public set — the leak SF-01 CB-3 closes.
    # `__init__` and `__repr__` are here too and stay: they are interface, not accident.
    "python": ["Store", "Store.__init__", "Store.__repr__", "Store.get", "Store.__mangled", "free"],
    # `Shape.area` and `Shape.name` are ABSENT. Both are implicitly public by JLS; Java's filter
    # reads "no modifier" as hidden, which is right for a class and wrong for an interface.
    "java": ["Shape", "Circle", "Circle.area", "Circle.name"],
    "kotlin": ["Shape", "Shape.area", "Circle", "Circle.area", "free"],
    # `Circle.log` (protected) and `Circle.helper` (private) ARE HERE: TypeScript checks only
    # whether an ancestor is exported and never reads a member's accessibility modifier.
    "typescript": ["Circle", "Circle.area", "Circle.log", "Circle.helper", "free"],
    # Trait members absent, same cause as Java. `Circle.crate_only` is `pub(crate)` and is here.
    "rust": ["Shape", "Circle", "Circle.area", "Circle.crate_only", "free"],
    "go": ["Circle", "Circle.Area", "Free"],
    # EMPTY. C's filter is `return visibility is None`, so any request answers with silence.
    "c": [],
    "cpp": ["Widget", "Widget.visible", "Plain", "Plain.open", "free_fn"],
    "sql": _SQL_ALL,
    "markdown": _MD_ALL,
}

#: What a request for a level OTHER than `public` returns today. Nine of the ten ignore it entirely
#: and hand back the whole file — the fail-open `FR-2` exists to close. C++ is the one that filters.
FAILS_OPEN_TO: dict[str, list[str]] = {
    "python": _PY_ALL,
    "java": _JAVA_ALL,
    "kotlin": _KT_ALL,
    "typescript": _TS_ALL,
    "rust": _RS_ALL,
    "go": _GO_ALL,
    "sql": _SQL_ALL,
    "markdown": _MD_ALL,
    "c": [],
}


#: A decorated symbol beside an undecorated one, for the five languages that have the concept.
#: Without this, every `decorator_filter` assertion would be "returns nothing" against a fixture
#: containing no decorators — true for free, and blind to a filter that rejects everything.
DECORATED: dict[str, str] = {
    "python": "import x\n\n@x.Inject\ndef wired(): return 1\n\ndef plain(): return 2\n",
    "java": "public class W {\n  @Inject public void wired() {}\n  public void plain() {}\n}\n",
    "kotlin": "class W {\n  @Inject fun wired() {}\n  fun plain() {}\n}\n",
    "typescript": "export class W {\n  @Inject wired(): void {}\n  plain(): void {}\n}\n",
    "rust": "#[Inject]\npub fn wired() -> i32 { 1 }\npub fn plain() -> i32 { 2 }\n",
}

#: What `decorator_filter` does to the main fixtures, which carry no decorators at all. Three
#: parsers do something other than "return the matching ones", and all three are deliberate.
UNDECORATED_UNDER_FILTER: dict[str, list[str]] = {
    "cpp": [],
    "go": [],  # a hard `return False` — "Go does not have decorators"
    "java": [],
    "kotlin": [],
    "python": [],
    "rust": [],
    "typescript": [],
    "markdown": _MD_ALL,  # ignores the filter entirely
    "sql": _SQL_ALL,  # ignores it too
}


#: Both filters at once, measured 2026-08-26. Literals, so the assertion cannot be satisfied by
#: two broken calls agreeing with each other.
BOTH_FILTERS: dict[str, list[str]] = {
    "python": ["wired"],
    "java": ["W.wired"],
    "kotlin": ["W.wired"],
    "typescript": ["W.wired"],
    "rust": ["wired"],
}


class TestListSymbolsDecoratorFilter:
    """`decorator_filter` shares `_is_symbol_valid` with visibility, and SF-01 CB-3 DELETES four
    copies of that function.

    Nothing pinned this before. C raises on purpose and Go returns nothing on purpose; both
    behaviours live inside functions the next boundary removes, and both would have gone silently.
    Found by the pre-commit Phase 2 test-gap analysis, not by the plan.
    """

    @pytest.mark.parametrize("lang", sorted(DECORATED), ids=str)
    def test_the_filter_keeps_the_decorated_symbol(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Happy path] The half that cannot pass for free: a matching symbol survives."""
        kept = parsers[lang].list_symbols(DECORATED[lang], decorator_filter="Inject")
        assert [s for s in kept if s.endswith("wired")] == kept
        assert kept != []

    @pytest.mark.parametrize("lang", sorted(DECORATED), ids=str)
    def test_the_filter_drops_the_undecorated_neighbour(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Happy path] The control. Its neighbour is in the unfiltered listing and not here."""
        code = DECORATED[lang]
        assert any(s.endswith("plain") for s in parsers[lang].list_symbols(code))
        assert not any(
            s.endswith("plain") for s in parsers[lang].list_symbols(code, decorator_filter="Inject")
        )

    @pytest.mark.parametrize("lang", sorted(BOTH_FILTERS), ids=str)
    def test_both_filters_together_still_keep_the_decorated_symbol(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] The combination CB-3's rewrite must preserve. One function answers both
        questions, so a rewrite that gets either wrong shows up here.

        Asserted against a **literal**, not against the same call with one argument removed. The
        first draft compared the unit with itself, which passes whenever both halves break the
        same way — the vacuous shape `test-quality.md` calls pattern 7, found by the Phase 7.5
        review of this very file.
        """
        assert (
            parsers[lang].list_symbols(
                DECORATED[lang], visibility=["public"], decorator_filter="Inject"
            )
            == BOTH_FILTERS[lang]
        )

    @pytest.mark.parametrize("lang", sorted(UNDECORATED_UNDER_FILTER), ids=str)
    def test_a_fixture_with_no_decorators_under_the_filter(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] markdown and SQL ignore `decorator_filter` outright and return everything.
        Pinned so removing their inherited filter is a visible change rather than a quiet one."""
        assert (
            parsers[lang].list_symbols(FIXTURES[lang], decorator_filter="Inject")
            == UNDECORATED_UNDER_FILTER[lang]
        )

    def test_c_refuses_the_filter_rather_than_answering_it(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Hostile] C raises instead of returning a wrong answer — `c/codestructure.py:84`.

        The one parser that treats an unsupported filter as an error. It is the right call and it
        is undocumented anywhere else, so CB-3 must not delete it by accident.
        """
        from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

        with pytest.raises(CodeStructureError):
            parsers["c"].list_symbols(FIXTURES["c"], decorator_filter="Inject")

    def test_go_rejects_every_symbol_because_go_has_no_decorators(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Hostile] Go answers with nothing rather than raising — `go/codestructure.py:129`.

        Stated separately from the table above because it is a deliberate `return False`, not an
        absence of decorated symbols, and the two are indistinguishable in a count.
        """
        assert parsers["go"].list_symbols(FIXTURES["go"], decorator_filter="Inject") == []
        assert parsers["go"].list_symbols(FIXTURES["go"]) != []


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


@pytest.mark.parametrize("lang", sorted(FAILS_OPEN_TO), ids=str)
@pytest.mark.parametrize("request_", [["protected"], ["private"], ["nonsense"]], ids=lambda r: r[0])
class TestListSymbolsFailsOpen:
    """[Hostile] Asking for anything but `public` returns the WHOLE FILE on nine of ten parsers.

    Pinned because it is the defect, not despite it. `FR-2` inverts this and the diff to these
    literals is how that change is read in review.
    """

    def test_a_non_public_request_is_ignored(
        self, parsers: dict[str, typing.Any], lang: str, request_: list[str]
    ) -> None:
        assert (
            parsers[lang].list_symbols(FIXTURES[lang], visibility=request_) == FAILS_OPEN_TO[lang]
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

    def test_an_empty_visibility_list_is_falsy_and_filters_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] `[]` is falsy, so today it means *no filter* rather than *nothing matches*.

        C and C++ are the exceptions and return nothing. Neither tests truthiness: C++ tests
        membership, and C asks `visibility is None`, so an empty list reads as *a filter was
        requested* and drops everything. Three behaviours from one input is exactly what one
        shared filter removes.

        Measured, not reasoned: the first draft of this test predicted C would behave like the
        other eight and it does not.
        """
        expected: list[str] = [] if lang in {"cpp", "c"} else UNFILTERED[lang]
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=[]) == expected

    def test_unparseable_source_degrades_without_raising(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Graceful degradation] tree-sitter is error-tolerant, so nonsense yields few or no
        symbols rather than an exception. A parser that raises here would take a whole scan down."""
        symbols = parsers[lang].list_symbols("<<<< not %% any known ~~~ language >>>>")
        assert isinstance(symbols, list)
