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

    #: `RunContext` is being cut down from 32 fields to a size that clears the god-object
    #: limit, one group of related fields at a time. This asserts an EXACT count rather than
    #: an upper bound, so it fails in both directions: adding a field fails, and so does a
    #: step that claims to have removed fields but left them in place.
    #:
    #: Lower it as each group lands. Remaining: 22 -> 19 (graph fields) -> 15 (dead fields
    #: dropped, constitution/standards paired). 15 is the limit, so the last step is the one
    #: that stops this file being reported.
    EXPECTED_RUN_CONTEXT_ATTRIBUTES = 22

    def test_run_context_attribute_count_matches_the_expected_step(self, ch: ModuleType) -> None:
        path = REPO_ROOT / "src" / "specweaver" / "core" / "flow" / "handlers" / "base.py"
        reports = ch.analyse_file(path)

        run_context = next(r for r in reports if r.name == "RunContext")

        assert len(run_context.attributes) == self.EXPECTED_RUN_CONTEXT_ATTRIBUTES

    def test_run_context_is_still_over_the_god_object_limit(self, ch: ModuleType) -> None:
        """A deliberate record that the job is not finished yet.

        This file is still reported as a god object, as it was before the split began (33
        attributes then). The finding is long-standing and shrinking, not newly introduced and
        not suppressed. Keeping it asserted means nobody can lose track of that mid-way. DELETE
        this test with the step that finally brings the count to the limit — if it ever starts
        failing, that step succeeded.
        """
        path = REPO_ROOT / "src" / "specweaver" / "core" / "flow" / "handlers" / "base.py"
        reports = ch.analyse_file(path)

        run_context = next(r for r in reports if r.name == "RunContext")

        assert run_context.too_many_attributes(ch.MAX_ATTRIBUTES)

    @pytest.mark.parametrize(
        "extracted",
        ["IsolationPolicy", "PlanContext", "ModelAccess", "RunHandle", "AnalysisContext"],
    )
    def test_the_extracted_sub_models_are_not_god_objects(
        self, ch: ModuleType, extracted: str
    ) -> None:
        """The point of the split: what comes OUT of `RunContext` must not repeat the problem.

        Listed by name so each new group has to be added here deliberately, rather than the
        check silently covering only the first one that was extracted.
        """
        path = REPO_ROOT / "src" / "specweaver" / "core" / "flow" / "handlers" / "base.py"
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
