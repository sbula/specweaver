# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for validation pipeline inheritance resolution.

Tests extends/override/remove/add logic that resolves a child pipeline
against its base into a flat step list.
"""

from __future__ import annotations

import pytest

from specweaver.validation.inheritance import resolve_pipeline
from specweaver.validation.pipeline import ValidationPipeline, ValidationStep

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE_STEPS = [
    ValidationStep(name="s01", rule="S01", params={"warn": 1}),
    ValidationStep(name="s02", rule="S02"),
    ValidationStep(name="s04", rule="S04"),
    ValidationStep(name="s05", rule="S05", params={"warn_threshold": 30, "fail_threshold": 60}),
    ValidationStep(name="s08", rule="S08", params={"warn_threshold": 3}),
]

_BASE = ValidationPipeline(
    name="base_pipeline",
    steps=_BASE_STEPS,
)


def _base_loader(name: str) -> ValidationPipeline:
    """Mock loader that returns the base pipeline."""
    if name == "base_pipeline":
        return _BASE
    msg = f"Pipeline '{name}' not found"
    raise FileNotFoundError(msg)


# ---------------------------------------------------------------------------
# No inheritance (passthrough)
# ---------------------------------------------------------------------------


class TestNoInheritance:
    """Pipeline with no extends returns its own steps."""

    def test_standalone_pipeline(self):
        """Pipeline without extends keeps its own steps."""
        pipeline = ValidationPipeline(
            name="standalone",
            steps=[
                ValidationStep(name="s01", rule="S01"),
                ValidationStep(name="s02", rule="S02"),
            ],
        )
        resolved = resolve_pipeline(pipeline, _base_loader)
        assert len(resolved.steps) == 2
        assert resolved.steps[0].rule == "S01"


# ---------------------------------------------------------------------------
# extends
# ---------------------------------------------------------------------------


class TestExtends:
    """Test extends — inherit all steps from base."""

    def test_extends_copies_base_steps(self):
        """Child with extends and no modifications gets all base steps."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
        )
        resolved = resolve_pipeline(child, _base_loader)
        assert len(resolved.steps) == 5
        assert [s.rule for s in resolved.steps] == ["S01", "S02", "S04", "S05", "S08"]

    def test_extends_preserves_base_params(self):
        """Base step params are preserved in inherited pipeline."""
        child = ValidationPipeline(name="child", steps=[], extends="base_pipeline")
        resolved = resolve_pipeline(child, _base_loader)
        s05 = resolved.get_step("s05")
        assert s05.params["warn_threshold"] == 30

    def test_extends_nonexistent_raises(self):
        """Extending a non-existent base raises FileNotFoundError."""
        child = ValidationPipeline(name="child", steps=[], extends="nonexistent")
        with pytest.raises(FileNotFoundError):
            resolve_pipeline(child, _base_loader)


# ---------------------------------------------------------------------------
# override
# ---------------------------------------------------------------------------


class TestOverride:
    """Test override — modify params on existing steps."""

    def test_override_params(self):
        """Override replaces params on named step."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            override={
                "s05": {"params": {"warn_threshold": 80, "fail_threshold": 90}},
            },
        )
        resolved = resolve_pipeline(child, _base_loader)
        s05 = resolved.get_step("s05")
        assert s05.params["warn_threshold"] == 80
        assert s05.params["fail_threshold"] == 90

    def test_override_partial_params(self):
        """Override merges with existing params (doesn't drop unmentioned keys)."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            override={
                "s05": {"params": {"warn_threshold": 80}},
            },
        )
        resolved = resolve_pipeline(child, _base_loader)
        s05 = resolved.get_step("s05")
        assert s05.params["warn_threshold"] == 80
        # fail_threshold should still be there from base
        assert s05.params["fail_threshold"] == 60

    def test_override_nonexistent_step_raises(self):
        """Overriding a step that doesn't exist in base raises ValueError."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            override={
                "nonexistent": {"params": {"x": 1}},
            },
        )
        with pytest.raises(ValueError, match="nonexistent"):
            resolve_pipeline(child, _base_loader)


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


class TestRemove:
    """Test remove — drop steps from base."""

    def test_remove_single(self):
        """Remove a single step from base."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            remove=["s04"],
        )
        resolved = resolve_pipeline(child, _base_loader)
        assert len(resolved.steps) == 4
        assert all(s.name != "s04" for s in resolved.steps)

    def test_remove_multiple(self):
        """Remove multiple steps."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            remove=["s04", "s08"],
        )
        resolved = resolve_pipeline(child, _base_loader)
        assert len(resolved.steps) == 3
        names = [s.name for s in resolved.steps]
        assert "s04" not in names
        assert "s08" not in names

    def test_remove_nonexistent_raises(self):
        """Removing a step that doesn't exist raises ValueError."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            remove=["nonexistent"],
        )
        with pytest.raises(ValueError, match="nonexistent"):
            resolve_pipeline(child, _base_loader)


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


class TestAdd:
    """Test add — insert new steps into the pipeline."""

    def test_add_at_end(self):
        """Add without placement appends at end."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            add=[{"name": "d01", "rule": "D01", "params": {"strict": True}}],
        )
        resolved = resolve_pipeline(child, _base_loader)
        assert len(resolved.steps) == 6
        assert resolved.steps[-1].name == "d01"
        assert resolved.steps[-1].rule == "D01"
        assert resolved.steps[-1].params["strict"] is True

    def test_add_after(self):
        """Add with 'after' places step right after the named step."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            add=[{"name": "d01", "rule": "D01", "after": "s02"}],
        )
        resolved = resolve_pipeline(child, _base_loader)
        names = [s.name for s in resolved.steps]
        assert names.index("d01") == names.index("s02") + 1

    def test_add_before(self):
        """Add with 'before' places step right before the named step."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            add=[{"name": "d01", "rule": "D01", "before": "s04"}],
        )
        resolved = resolve_pipeline(child, _base_loader)
        names = [s.name for s in resolved.steps]
        assert names.index("d01") == names.index("s04") - 1

    def test_add_after_nonexistent_raises(self):
        """Add with 'after' referencing nonexistent step raises ValueError."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            add=[{"name": "d01", "rule": "D01", "after": "nonexistent"}],
        )
        with pytest.raises(ValueError, match="nonexistent"):
            resolve_pipeline(child, _base_loader)


# ---------------------------------------------------------------------------
# Combined operations
# ---------------------------------------------------------------------------


class TestCombined:
    """Test combined extends + override + remove + add."""

    def test_all_operations(self):
        """All inheritance operations applied together."""
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base_pipeline",
            override={"s05": {"params": {"warn_threshold": 80}}},
            remove=["s04"],
            add=[{"name": "d01", "rule": "D01", "after": "s02"}],
        )
        resolved = resolve_pipeline(child, _base_loader)

        # Base had 5 steps, removed 1, added 1 = 5 steps
        assert len(resolved.steps) == 5

        # s04 removed
        names = [s.name for s in resolved.steps]
        assert "s04" not in names

        # d01 added after s02
        assert names.index("d01") == names.index("s02") + 1

        # s05 override applied
        s05 = resolved.get_step("s05")
        assert s05.params["warn_threshold"] == 80
        assert s05.params["fail_threshold"] == 60  # unchanged from base


# ---------------------------------------------------------------------------
# Circular extends detection (#5)
# ---------------------------------------------------------------------------


class TestCircularExtends:
    """Edge case: circular extends chains must be detected."""

    def test_direct_self_reference(self):
        """Pipeline that extends itself raises ValueError."""
        pipeline = ValidationPipeline(
            name="self_ref",
            steps=[],
            extends="self_ref",
        )

        def _loader(name: str) -> ValidationPipeline:
            if name == "self_ref":
                return pipeline
            msg = f"Not found: {name}"
            raise FileNotFoundError(msg)

        with pytest.raises(ValueError, match="Circular extends"):
            resolve_pipeline(pipeline, _loader)

    def test_indirect_circular_chain(self):
        """A extends B extends A raises ValueError."""
        pipeline_a = ValidationPipeline(
            name="pipeline_a", steps=[], extends="pipeline_b",
        )
        pipeline_b = ValidationPipeline(
            name="pipeline_b", steps=[], extends="pipeline_a",
        )

        def _loader(name: str) -> ValidationPipeline:
            if name == "pipeline_a":
                return pipeline_a
            if name == "pipeline_b":
                return pipeline_b
            msg = f"Not found: {name}"
            raise FileNotFoundError(msg)

        with pytest.raises(ValueError, match="Circular extends"):
            resolve_pipeline(pipeline_a, _loader)

    def test_three_level_circular(self):
        """A extends B extends C extends A raises ValueError."""
        a = ValidationPipeline(name="a", steps=[], extends="b")
        b = ValidationPipeline(name="b", steps=[], extends="c")
        c = ValidationPipeline(name="c", steps=[], extends="a")

        pipelines = {"a": a, "b": b, "c": c}

        def _loader(name: str) -> ValidationPipeline:
            if name in pipelines:
                return pipelines[name]
            msg = f"Not found: {name}"
            raise FileNotFoundError(msg)

        with pytest.raises(ValueError, match="Circular extends"):
            resolve_pipeline(a, _loader)

    def test_deep_non_circular_chain_works(self):
        """Non-circular multi-level chain resolves correctly."""
        grandparent = ValidationPipeline(
            name="grandparent",
            steps=[ValidationStep(name="s01", rule="S01")],
        )
        parent = ValidationPipeline(
            name="parent", steps=[], extends="grandparent",
        )
        child = ValidationPipeline(
            name="child", steps=[], extends="parent",
        )

        pipelines = {"grandparent": grandparent, "parent": parent}

        def _loader(name: str) -> ValidationPipeline:
            if name in pipelines:
                return pipelines[name]
            msg = f"Not found: {name}"
            raise FileNotFoundError(msg)

        resolved = resolve_pipeline(child, _loader)
        assert len(resolved.steps) == 1
        assert resolved.steps[0].rule == "S01"


# ---------------------------------------------------------------------------
# Duplicate step names (#8)
# ---------------------------------------------------------------------------


class TestDuplicateStepNames:
    """Edge case: duplicate step names in a pipeline."""

    def test_get_step_returns_first_match(self):
        """get_step() returns the first step with the given name."""
        pipeline = ValidationPipeline(
            name="dup",
            steps=[
                ValidationStep(name="s01", rule="S01", params={"warn": 1}),
                ValidationStep(name="s01", rule="S01", params={"warn": 99}),
            ],
        )
        step = pipeline.get_step("s01")
        assert step is not None
        assert step.params["warn"] == 1  # first match

    def test_override_applies_to_first_match(self):
        """Override on duplicate name applies to the first occurrence."""
        base = ValidationPipeline(
            name="base",
            steps=[
                ValidationStep(name="s01", rule="S01", params={"warn": 1}),
                ValidationStep(name="dup", rule="S02", params={"x": 1}),
                ValidationStep(name="dup", rule="S03", params={"x": 2}),
            ],
        )
        child = ValidationPipeline(
            name="child",
            steps=[],
            extends="base",
            override={"dup": {"params": {"x": 99}}},
        )

        def _loader(name: str) -> ValidationPipeline:
            return base

        resolved = resolve_pipeline(child, _loader)
        # First "dup" gets override, second keeps original
        dups = [s for s in resolved.steps if s.name == "dup"]
        assert len(dups) == 2
        assert dups[0].params["x"] == 99
        assert dups[1].params["x"] == 2

