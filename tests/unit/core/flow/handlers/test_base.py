# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from specweaver.core.flow.handlers.base import IsolationPolicy, PlanContext, RunContext
from specweaver.infrastructure.llm.models import ProjectMetadata


def test_run_context_builds_project_metadata(tmp_path: Path) -> None:
    """Test that RunContext correctly builds the metadata DTO."""
    (tmp_path / "context.yaml").write_text("archetype: web-service\n", encoding="utf-8")

    config = MagicMock()
    config.validation.overrides = {"S01": True}
    llm = MagicMock()
    llm.provider_name = "mock_provider"
    llm.model = "mock-model"
    db = MagicMock()

    context = RunContext(
        llm=llm,
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
        db=db,
        config=config,
    )

    assert isinstance(context.project_metadata, ProjectMetadata)
    assert context.project_metadata.project_name == tmp_path.name
    assert context.project_metadata.safe_config.llm_model == "mock-model"
    assert context.project_metadata.safe_config.llm_provider == "mock_provider"
    assert context.project_metadata.safe_config.validation_rules == {"S01": True}
    assert context.project_metadata.archetype == "web-service"


def test_run_context_graceful_degradation(tmp_path: Path) -> None:
    """Test fallback when platform module raises an exception."""
    config = MagicMock()
    config.validation = MagicMock()
    config.validation.overrides = {}
    llm = MagicMock()
    llm.provider_name = "test"
    llm.model = "test"
    db = MagicMock()

    with patch("platform.platform", side_effect=Exception("err")):
        context = RunContext(
            llm=llm,
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            db=db,
            config=config,
        )

    assert context.project_metadata.language_target == "Unknown Environment"


def test_run_context_env_vars(tmp_path: Path) -> None:
    """Test that RunContext safely holds isolated env_vars boundaries natively."""
    context = RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
        pipeline_name="decomposition_flow",
        env_vars={"SW_PORT_OFFSET": "49551"},
    )

    # Must natively survive pydantic model dumping
    data = context.model_dump()
    assert context.pipeline_name == "decomposition_flow"
    assert context.env_vars == {"SW_PORT_OFFSET": "49551"}
    assert data["env_vars"] == {"SW_PORT_OFFSET": "49551"}

    # Default fallback
    context_default = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    assert context_default.env_vars == {}
    assert context_default.pipeline_name is None


def test_run_context_isolation_fields_default(tmp_path: Path) -> None:
    """INT-US-09 T5: execution_root defaults to None (callers fall back to project_path);
    enforce_isolation defaults to False (opt-in policy off).

    TECH-006 SF-02 (FR-6): both now live on the nested `isolation` sub-model. The asserted
    behaviour is unchanged — only the path to it is.
    """
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    assert context.isolation.execution_root is None
    assert context.isolation.enforce_isolation is False

    # execution_root can carry the worktree path.
    wt = tmp_path / ".worktrees" / "task-1"
    ctx2 = RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
        isolation=IsolationPolicy(execution_root=wt),
    )
    assert ctx2.isolation.execution_root == wt


class TestIsolationPolicy:
    """TECH-006 SF-02 CB1 (FR-6, FR-12, NFR-6, NFR-8, AD-8): the five worktree-isolation
    fields move off `RunContext`'s flat surface into one frozen, extra-forbidding sub-model."""

    # --- [Happy Path] ------------------------------------------------------

    def test_defaults_match_the_previous_flat_defaults_exactly(self) -> None:
        """D-3: relocation only — every default is byte-identical to the flat field's."""
        policy = IsolationPolicy()
        assert policy.enforce_isolation is False
        assert policy.execution_root is None
        assert policy.session_isolation is False
        assert policy.allowed_paths == []
        assert policy.dal_level is None

    def test_run_context_gets_a_default_policy_without_being_given_one(
        self, tmp_path: Path
    ) -> None:
        """Every minimal-construction call site (the API passes 3 kwargs) keeps working."""
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        assert isinstance(context.isolation, IsolationPolicy)
        assert context.isolation.enforce_isolation is False

    # --- [Boundary] --------------------------------------------------------

    def test_allowed_paths_default_factory_is_per_instance(self) -> None:
        """Carried over from the flat field: two policies must not share one list."""
        a = IsolationPolicy()
        a.allowed_paths.append("src/x.py")
        assert IsolationPolicy().allowed_paths == []

    def test_model_copy_returns_an_independent_instance(self, tmp_path: Path) -> None:
        """The exact mechanism NFR-8 depends on: a copy-then-reassign never touches the source."""
        original = IsolationPolicy()
        updated = original.model_copy(update={"execution_root": tmp_path / "wt"})
        assert updated is not original
        assert updated.execution_root == tmp_path / "wt"
        assert original.execution_root is None

    def test_model_copy_carries_every_unlisted_field_through(self, tmp_path: Path) -> None:
        """A partial update must not silently reset the fields it does not name."""
        original = IsolationPolicy(session_isolation=True, allowed_paths=["src/a.py"])
        updated = original.model_copy(update={"execution_root": tmp_path})
        assert updated.session_isolation is True
        assert updated.allowed_paths == ["src/a.py"]

    # --- [Graceful Degradation] -------------------------------------------

    def test_policy_survives_a_shallow_copy_of_its_run_context(self, tmp_path: Path) -> None:
        """`runner_utils` worktree isolation uses `copy.copy(context)`, NOT `model_copy`.
        The shallow copy SHARES the policy instance — reassigning the whole attribute on the
        copy is the only safe update, and it must leave the original's policy untouched."""
        import copy

        original = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        isolated = copy.copy(original)
        assert isolated.isolation is original.isolation  # shallow: shared by reference

        isolated.isolation = isolated.isolation.model_copy(
            update={"execution_root": tmp_path / "wt"}
        )
        assert isolated.isolation is not original.isolation
        assert original.isolation.execution_root is None

    # --- [Hostile / Wrong Input] ------------------------------------------

    def test_direct_field_mutation_raises(self, tmp_path: Path) -> None:
        """AD-8: frozen closes the RED-1.3 shallow-copy corruption bug class structurally."""
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        with pytest.raises(ValidationError):
            context.isolation.execution_root = tmp_path / "wt"

    def test_unknown_kwarg_on_the_policy_raises(self) -> None:
        """FR-12: `extra="forbid"` — a typo'd kwarg must never be silently dropped."""
        with pytest.raises(ValidationError):
            IsolationPolicy(bogus=1)

    def test_unknown_kwarg_on_run_context_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", bogus=1)

    def test_old_flat_kwarg_raises_instead_of_being_dropped(self, tmp_path: Path) -> None:
        """NFR-6 half 1: a missed migration at a CONSTRUCTION site fails loudly."""
        with pytest.raises(ValidationError):
            RunContext(
                project_path=tmp_path, spec_path=tmp_path / "spec.md", enforce_isolation=True
            )

    def test_old_flat_attribute_read_raises(self, tmp_path: Path) -> None:
        """NFR-6 half 2: a missed migration at an ATTRIBUTE-READ site fails loudly."""
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        for gone in ("enforce_isolation", "execution_root", "session_isolation", "allowed_paths"):
            with pytest.raises(AttributeError):
                getattr(context, gone)

    def test_wrong_types_still_rejected_at_the_new_path(self) -> None:
        """The two hostile-input guarantees `test_run_context_session_fields` made flatly."""
        with pytest.raises(ValidationError):
            IsolationPolicy(session_isolation="yes-please")
        with pytest.raises(ValidationError):
            IsolationPolicy(allowed_paths="src/foo.py")  # a bare str, not a list

    def test_isolation_is_not_nullable(self, tmp_path: Path) -> None:
        """RED-2.3: proves the degenerate `isolation=None` shape is unreachable in production,
        so `resolve_should_isolate`'s tolerance of it is belt-and-braces, not a live path."""
        with pytest.raises(ValidationError):
            RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", isolation=None)


class TestPlanContext:
    """TECH-006 SF-02 CB2 (FR-6, FR-10, AD-8): the two plan concepts move into one frozen
    sub-model. INT-US-21 AD-1's rule that they are DISTINCT and must not be reconflated is
    unchanged by the move — it is now expressed by the sub-model's own shape."""

    # --- [Happy Path] ------------------------------------------------------

    def test_defaults_match_the_previous_flat_defaults(self) -> None:
        plan_context = PlanContext()
        assert plan_context.plan is None
        assert plan_context.decomposition is None

    def test_run_context_gets_a_default_plan_context(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        assert isinstance(context.plan_context, PlanContext)
        assert context.plan_context.plan is None

    # --- [Boundary] --------------------------------------------------------

    def test_the_two_fields_stay_independent(self, tmp_path: Path) -> None:
        """INT-US-21 AD-1: `plan` is the implementation PlanArtifact, `decomposition` is the
        DecompositionPlan JSON. Setting one must never imply the other — the exact
        reconflation the AD-1 comment exists to prevent."""
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")

        context.plan_context = context.plan_context.model_copy(update={"plan": "impl"})

        assert context.plan_context.plan == "impl"
        assert context.plan_context.decomposition is None

    def test_clearing_one_field_leaves_the_other_intact(self, tmp_path: Path) -> None:
        """`hydration.py` clears exactly one of the pair on FAILED/ERROR (FR-10). Under a
        frozen sub-model that clear is a `model_copy`, which must not reset its sibling."""
        original = PlanContext(plan="impl", decomposition='{"components": []}')

        cleared = original.model_copy(update={"decomposition": None})

        assert cleared.decomposition is None
        assert cleared.plan == "impl"
        assert original.decomposition == '{"components": []}'

    # --- [Hostile / Wrong Input] ------------------------------------------

    def test_direct_field_mutation_raises(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        with pytest.raises(ValidationError):
            context.plan_context.plan = "impl"

    def test_unknown_kwarg_raises(self) -> None:
        with pytest.raises(ValidationError):
            PlanContext(bogus=1)

    def test_old_flat_kwargs_raise_instead_of_being_dropped(self, tmp_path: Path) -> None:
        for gone in ("plan", "decomposition"):
            with pytest.raises(ValidationError):
                RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", **{gone: "x"})

    def test_old_flat_attribute_reads_raise(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        for gone in ("plan", "decomposition"):
            with pytest.raises(AttributeError):
                getattr(context, gone)

    def test_plan_context_is_not_nullable(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", plan_context=None)
