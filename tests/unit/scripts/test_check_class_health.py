# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the class-health guard (`scripts/check_class_health.py`).

Two metrics with different failure modes, so both are pinned against known-good and known-bad
input. The LCOM4 cases in particular lock in the exclusion rules: the first version of this check
scored a parser class at LCOM4=19 because every property accessor counted as its own component,
which is a number nobody can act on.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ch() -> ModuleType:
    return _load("check_class_health")


def _analyse(ch: ModuleType, source: str) -> object:
    tree = ast.parse(source)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
    return ch.analyse_class(node, Path("synthetic.py"))


# ---------------------------------------------------------------------------
# Attribute counting — the god-object axis
# ---------------------------------------------------------------------------


class TestAttributeCount:
    def test_instance_attributes_assigned_in_init_are_counted(self, ch: ModuleType) -> None:
        report = _analyse(
            ch, "class C:\n    def __init__(self):\n        self.a = 1\n        self.b = 2\n"
        )

        assert report.attributes == {"a", "b"}

    def test_dataclass_style_annotations_are_counted(self, ch: ModuleType) -> None:
        """RunContext declares its fields in the class body, not in __init__."""
        report = _analyse(ch, "class C:\n    a: int\n    b: str\n    c: bool\n")

        assert report.attributes == {"a", "b", "c"}

    def test_methods_are_not_counted_as_attributes(self, ch: ModuleType) -> None:
        report = _analyse(
            ch,
            "class C:\n    def m(self):\n        return self.m()\n    def n(self):\n        return 1\n",
        )

        assert report.attributes == set()

    def test_a_class_at_the_limit_is_not_flagged(self, ch: ModuleType) -> None:
        source = "class C:\n" + "".join(f"    a{i}: int\n" for i in range(15))

        assert not _analyse(ch, source).too_many_attributes(15)

    def test_one_attribute_over_the_limit_is_flagged(self, ch: ModuleType) -> None:
        source = "class C:\n" + "".join(f"    a{i}: int\n" for i in range(16))

        assert _analyse(ch, source).too_many_attributes(15)

    def test_pydantic_model_config_is_not_counted(self, ch: ModuleType) -> None:
        """It is framework configuration, not state the class carries."""
        source = "class C:\n    model_config = ConfigDict(frozen=True)\n    a: int\n    b: str\n"

        assert _analyse(ch, source).attributes == {"a", "b"}

    def test_a_pydantic_class_gets_the_same_budget_as_any_other(self, ch: ModuleType) -> None:
        """Counting `model_config` would silently give Pydantic classes a budget of 14 while
        every other class gets 15 — a constant offset that says nothing about whether the
        class does too much."""
        plain = "class C:\n" + "".join(f"    a{i}: int\n" for i in range(15))
        pydantic = "class C:\n    model_config = ConfigDict()\n" + "".join(
            f"    a{i}: int\n" for i in range(15)
        )

        assert not _analyse(ch, plain).too_many_attributes(15)
        assert not _analyse(ch, pydantic).too_many_attributes(15)

    def test_sqlalchemy_table_declarations_are_not_counted(self, ch: ModuleType) -> None:
        """`__tablename__` and `__table_args__` are ORM wiring, not state the class carries.

        Same reasoning as `model_config`, and the same evidence: every one of the 13 mapped
        classes in `src` declares `__tablename__`, so counting it subtracts from every ORM class's
        budget and distinguishes none of them. `Task` was the one oversized class in the baseline
        at 16 — and has **14** real mapped columns, under the limit of 15. `TECH-035`.
        """
        source = (
            "class T(Base):\n"
            '    __tablename__ = "memory_tasks"\n'
            "    __table_args__ = (Index('i', 'a'),)\n"
            "    id: Mapped[int] = mapped_column(primary_key=True)\n"
        )

        assert _analyse(ch, source).attributes == {"id"}

    def test_a_dunder_that_is_not_orm_wiring_is_still_counted(self, ch: ModuleType) -> None:
        """The exemption is a named list, not "ignore every dunder"."""
        source = "class T:\n    __slots__ = ('a',)\n    a: int\n"

        assert _analyse(ch, source).attributes == {"__slots__", "a"}

    def test_a_field_merely_named_like_it_is_still_counted(self, ch: ModuleType) -> None:
        """Only the exact `model_config` name is exempt. A field called `model_configuration`
        is ordinary state and must not slip through on a prefix match."""
        source = "class C:\n    model_configuration: dict\n    a: int\n"

        assert _analyse(ch, source).attributes == {"model_configuration", "a"}

    def test_model_config_reached_through_self_is_also_ignored(self, ch: ModuleType) -> None:
        """The exemption must hold however the attribute is discovered — declared in the class
        body or touched via `self` inside a method — or the count depends on writing style."""
        source = "class C:\n    def m(self):\n        return self.model_config, self.real_state\n"

        assert _analyse(ch, source).attributes == {"real_state"}

    #: `RunContext` was cut from 32 fields to 15 by grouping related fields into small
    #: objects. 15 is exactly the god-object limit, so there is no headroom: the next field
    #: added directly to `RunContext` puts it over again.
    #:
    #: Asserted as an EXACT count, not an upper bound, so it fails in both directions — a new
    #: field fails, and so does a change that claims to remove one but does not. If you need a
    #: new field, put it in the group it belongs to rather than raising this number.
    EXPECTED_RUN_CONTEXT_ATTRIBUTES = 15

    def test_run_context_attribute_count_matches_the_expected_step(self, ch: ModuleType) -> None:
        # TECH-015 moved the context model out of `base.py`, which now holds only the
        # StepHandler Protocol. These assertions follow the models, not the filename.
        path = REPO_ROOT / "src" / "specweaver" / "core" / "flow" / "handlers" / "run_context.py"
        reports = ch.analyse_file(path)

        run_context = next(r for r in reports if r.name == "RunContext")

        assert len(run_context.attributes) == self.EXPECTED_RUN_CONTEXT_ATTRIBUTES

    @pytest.mark.parametrize(
        "extracted",
        [
            "IsolationPolicy",
            "PlanContext",
            "ModelAccess",
            "RunHandle",
            "AnalysisContext",
            "GraphContext",
            "GuidanceContent",
        ],
    )
    def test_the_extracted_sub_models_are_not_god_objects(
        self, ch: ModuleType, extracted: str
    ) -> None:
        """The point of the split: what comes OUT of `RunContext` must not repeat the problem.

        Listed by name so each new group has to be added here deliberately, rather than the
        check silently covering only the first one that was extracted.
        """
        # TECH-015 moved the context model out of `base.py`, which now holds only the
        # StepHandler Protocol. These assertions follow the models, not the filename.
        path = REPO_ROOT / "src" / "specweaver" / "core" / "flow" / "handlers" / "run_context.py"
        reports = ch.analyse_file(path)

        sub_model = next(r for r in reports if r.name == extracted)

        assert not sub_model.too_many_attributes(ch.MAX_ATTRIBUTES)


# ---------------------------------------------------------------------------
# LCOM4 — the "where do I cut it" axis
# ---------------------------------------------------------------------------


COHESIVE = """
class C:
    def __init__(self):
        self.shared = 0
    def a(self):
        return self.shared + 1
    def b(self):
        self.shared = 2
"""

TWO_CLASSES_IN_A_TRENCHCOAT = """
class C:
    def __init__(self):
        self.left = 0
        self.right = 0
    def read_left(self):
        return self.left
    def write_left(self):
        self.left = 1
    def read_right(self):
        return self.right
    def write_right(self):
        self.right = 1
"""


class TestLcom4:
    def test_methods_sharing_an_attribute_form_one_component(self, ch: ModuleType) -> None:
        assert _analyse(ch, COHESIVE).lcom4 == 1

    def test_two_independent_attribute_groups_score_two(self, ch: ModuleType) -> None:
        assert _analyse(ch, TWO_CLASSES_IN_A_TRENCHCOAT).lcom4 == 2

    def test_the_components_name_the_split(self, ch: ModuleType) -> None:
        """The output has to be a refactoring instruction, not just a score."""
        report = _analyse(ch, TWO_CLASSES_IN_A_TRENCHCOAT)

        assert sorted(sorted(c) for c in report.components) == [
            ["read_left", "write_left"],
            ["read_right", "write_right"],
        ]

    def test_methods_calling_each_other_are_one_component(self, ch: ModuleType) -> None:
        source = "class C:\n    def a(self):\n        return self.b()\n    def b(self):\n        return 1\n"

        assert _analyse(ch, source).lcom4 == 1

    def test_init_does_not_fuse_unrelated_groups(self, ch: ModuleType) -> None:
        """__init__ touches every attribute, so counting it reports perfect cohesion always."""
        assert _analyse(ch, TWO_CLASSES_IN_A_TRENCHCOAT).lcom4 == 2


class TestLcom4Exclusions:
    """These rules are what turned an unusable 98 findings into 22 actionable ones."""

    def test_a_constant_property_is_not_its_own_component(self, ch: ModuleType) -> None:
        source = COHESIVE + "    @property\n    def name(self):\n        return 'x'\n"

        assert _analyse(ch, source).lcom4 == 1

    def test_a_staticmethod_is_not_its_own_component(self, ch: ModuleType) -> None:
        source = COHESIVE + "    @staticmethod\n    def helper():\n        return 1\n"

        assert _analyse(ch, source).lcom4 == 1

    def test_an_abstract_stub_is_not_its_own_component(self, ch: ModuleType) -> None:
        source = COHESIVE + "    def contract(self):\n        ...\n"

        assert _analyse(ch, source).lcom4 == 1

    def test_a_not_implemented_stub_is_not_its_own_component(self, ch: ModuleType) -> None:
        source = COHESIVE + "    def contract(self):\n        raise NotImplementedError\n"

        assert _analyse(ch, source).lcom4 == 1

    def test_a_docstring_only_body_is_treated_as_a_stub(self, ch: ModuleType) -> None:
        source = COHESIVE + '    def contract(self):\n        """Just a docstring."""\n'

        assert _analyse(ch, source).lcom4 == 1

    def test_a_real_method_touching_state_still_counts(self, ch: ModuleType) -> None:
        """The exclusions must not swallow genuine incohesion."""
        source = COHESIVE + "    def other(self):\n        return self.unrelated\n"

        assert _analyse(ch, source).lcom4 == 2


#: An intent dispatcher: `run` reaches its handlers through `getattr`, which no static analysis
#: can resolve. `FileSystemAtom`, `GitAtom` and `QARunnerAtom` all have exactly this shape.
DISPATCHER = """
class C:
    def __init__(self, executor):
        self._executor = executor
    def run(self, context):
        handler = getattr(self, f"_intent_{context['intent']}", None)
        if handler is None:
            return sorted(self._known_intents())
        return handler(context)
    def _known_intents(self):
        return {n[8:] for n in dir(self) if n.startswith("_intent_")}
    def _intent_read(self, context):
        return self._executor.read(context)
    def _intent_write(self, context):
        return self._executor.write(context)
"""

#: Two public methods whose only coupling is a shared private helper that touches no attribute.
#: `GRPCParser` and `AsyncAPIParser` are exactly this.
COUPLED_THROUGH_A_HELPER = """
class C:
    def _parse(self, text):
        return text.split()
    def extract_endpoints(self, text):
        return [t for t in self._parse(text) if t.startswith("rpc")]
    def extract_messages(self, text):
        return [t for t in self._parse(text) if t.startswith("message")]
"""


class TestLcom4CouplingThroughExcludedMethods:
    """`TECH-035`. Graph *admission* and graph *edges* disagreed, and callers were stranded.

    `_is_stateless` admitted a method for calling a sibling, but edges were only drawn between
    methods both in the graph — so a method whose only sibling call was to a stateless helper was
    admitted and then left alone as its own component, inflating the score by one. It accounted for
    11 of the 19 classes frozen in the baseline.
    """

    def test_a_dispatcher_is_not_split_from_the_handlers_it_dispatches_to(
        self, ch: ModuleType
    ) -> None:
        """A metric that flips on whether a dispatcher publishes its intent list measures nothing.

        `getattr(self, ...)` is a call to *some* sibling; the analyser cannot say which, so the
        honest reading is that it may reach any of them.
        """
        assert _analyse(ch, DISPATCHER).lcom4 == 1

    def test_two_methods_coupled_only_through_a_helper_are_one_component(
        self, ch: ModuleType
    ) -> None:
        """They are coupled *through* `_parse`. Dropping it from the graph hid the edge."""
        assert _analyse(ch, COUPLED_THROUGH_A_HELPER).lcom4 == 1

    def test_a_class_with_no_instance_state_is_still_measured(self, ch: ModuleType) -> None:
        """The anti-blinding requirement: it must not collapse to "nothing to measure".

        An earlier candidate fix dropped stranded callers instead of connecting them, which scored
        four real classes at 0 — and `incohesive()` is `lcom4 > 1`, so 0 *passes*. That would have
        traded a false positive for a silent blind spot, which is this ticket's own subject.
        """
        report = _analyse(ch, COUPLED_THROUGH_A_HELPER)

        assert report.lcom4 == 1, "a stateless class must be measured, not skipped"
        assert report.components == [["_parse", "extract_endpoints", "extract_messages"]]

    def test_a_genuinely_split_class_is_still_split(self, ch: ModuleType) -> None:
        """The correction must not swallow the incohesion the metric exists to find."""
        assert _analyse(ch, TWO_CLASSES_IN_A_TRENCHCOAT).lcom4 == 2

    def test_a_dispatch_table_couples_the_methods_it_lists(self, ch: ModuleType) -> None:
        """Handing a sibling method around as a VALUE is coupling, exactly like calling it.

        `TSStandardsAnalyzer.get_extractors` returns `[self._extract_tsdoc, ...]`. Those are
        `ast.Attribute` loads, not `ast.Call`s, and the edge rule subtracted method names before
        comparing — so a dispatch table read as three unrelated classes.
        """
        source = (
            "class C(Base):\n"
            "    def get_extractors(self):\n"
            "        return [self._inherited_one, self._extract_a, self._extract_b]\n"
            "    def _extract_a(self, files):\n"
            "        return self._inherited_two(files)\n"
            "    def _extract_b(self, files):\n"
            "        return self._inherited_three(files)\n"
        )

        report = _analyse(ch, source)

        assert report.lcom4 == 1, f"a dispatch table read as {report.components}"

    def test_a_property_returning_a_class_constant_is_not_its_own_component(
        self, ch: ModuleType
    ) -> None:
        """`return self.NO_ROLE` is as stateless as `return "no_role"` — it is not instance state.

        `MCPExplorerTool.role` returns `BaseTool.NO_ROLE`, a class-level `str` constant. The
        existing exclusion covered a literal return and missed the constant that names it.
        """
        source = COHESIVE + "    @property\n    def role(self):\n        return self.NO_ROLE\n"

        assert _analyse(ch, source).lcom4 == 1

    def test_a_property_returning_instance_state_is_still_counted(self, ch: ModuleType) -> None:
        """The class-constant rule must not swallow a real accessor for real state."""
        source = COHESIVE + "    @property\n    def other(self):\n        return self._other\n"

        assert _analyse(ch, source).lcom4 == 2

    def test_a_nested_class_s_self_is_not_the_outer_method_s(self, ch: ModuleType) -> None:
        """`ast.walk` does not stop at a scope boundary, so an inner `self` leaked outward.

        `MarkdownCodeStructure._find_target_block` touches no state at all — it builds a local
        `MarkdownBodyBlock` whose `__init__` assigns `self.start_byte` and three more. Those four
        were attributed to the enclosing method, which made a stateless helper look like its own
        component AND added four phantom attributes to the god-object count. `TECH-035`.
        """
        source = (
            "class C:\n"
            "    def build(self, a, b):\n"
            "        class Inner:\n"
            "            def __init__(self, x):\n"
            "                self.start_byte = x\n"
            "                self.end_byte = x\n"
            "        return Inner(a)\n"
        )

        report = _analyse(ch, source)

        assert report.attributes == set(), f"nested self leaked: {sorted(report.attributes)}"

    def test_a_nested_function_s_self_is_not_the_outer_method_s(self, ch: ModuleType) -> None:
        """The same boundary, for a closure rather than a class."""
        source = (
            "class C:\n"
            "    def build(self):\n"
            "        def inner(self):\n"
            "            return self.leaked\n"
            "        return inner\n"
        )

        assert _analyse(ch, source).attributes == set()

    def test_a_closure_writes_to_the_enclosing_self(self, ch: ModuleType) -> None:
        """A nested `def` with NO `self` parameter captures the outer one — its writes count.

        The opposite error to the leak, and it was made first: skipping every nested scope
        decoupled `EventBridge.start_run` from `get_result`, because the write to `self._results`
        happens inside exactly such a closure. Both methods must stay in one component.
        """
        source = (
            "class C:\n"
            "    def start(self):\n"
            "        async def _wrapper():\n"
            "            self._results['k'] = 1\n"
            "        return _wrapper\n"
            "    def get_result(self):\n"
            "        return self._results.get('k')\n"
        )

        report = _analyse(ch, source)

        assert report.lcom4 == 1, f"a closure's write was not seen: {report.components}"
        assert report.attributes == {"_results"}

    def test_the_outer_method_s_own_state_still_counts(self, ch: ModuleType) -> None:
        """The boundary must not swallow what the method itself touches."""
        source = (
            "class C:\n"
            "    def build(self):\n"
            "        value = self._real\n"
            "        class Inner:\n"
            "            def __init__(self):\n"
            "                self.ignored = 1\n"
            "        return Inner(), value\n"
        )

        assert _analyse(ch, source).attributes == {"_real"}


class TestExemptions:
    def test_enum_members_are_not_god_object_attributes(self, ch: ModuleType) -> None:
        source = "class C(Enum):\n" + "".join(f"    M{i} = {i}\n" for i in range(40))

        assert ch.analyse_file  # module loaded
        tree = ast.parse(source)
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert ch._base_names(node) & ch.EXEMPT_BASES

    def test_protocol_classes_are_exempt(self, ch: ModuleType) -> None:
        tree = ast.parse("class C(Protocol):\n    pass\n")
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))

        assert ch._base_names(node) & ch.EXEMPT_BASES


class TestDegradation:
    def test_unparseable_file_yields_no_reports_rather_than_crashing(
        self, ch: ModuleType, tmp_path: Path
    ) -> None:
        bad = tmp_path / "broken.py"
        bad.write_text("class C(:\n", encoding="utf-8")

        assert ch.analyse_file(bad) == []

    def test_missing_path_blocks(self, ch: ModuleType, tmp_path: Path) -> None:
        assert ch.main([str(tmp_path / "nope")]) == 1

    def test_a_clean_tree_passes(self, ch: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "ok.py").write_text(COHESIVE, encoding="utf-8")

        assert ch.main([str(tmp_path)]) == 0

    def test_a_god_object_blocks(self, ch: ModuleType, tmp_path: Path) -> None:
        source = "class C:\n" + "".join(f"    a{i}: int\n" for i in range(40))
        (tmp_path / "fat.py").write_text(source, encoding="utf-8")

        assert ch.main([str(tmp_path)]) == 1

    def test_a_class_with_no_measurable_cohesion_is_said_out_loud(
        self, ch: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`TECH-035`. `incohesive()` is `lcom4 > 1`, so a score of 0 PASSES.

        An abstract base whose every method is a stub has nothing for cohesion to be *of*, and
        that is a fair reading — but "I could not measure this" and "I measured this and it was
        fine" must not look identical on the way out. Reported, not blocked: 28 classes in `src`
        are legitimately in this state.
        """
        (tmp_path / "abstract.py").write_text(
            "class C:\n"
            "    def read(self):\n        ...\n"
            "    def write(self):\n        raise NotImplementedError\n",
            encoding="utf-8",
        )

        assert ch.main([str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "no instance state" in out, f"a stateless class passed silently:\n{out}"
        assert "1 class(es)" in out
