# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from specweaver.core.flow.handlers.base import (
    AnalysisContext,
    GraphContext,
    GuidanceContent,
    IsolationPolicy,
    ModelAccess,
    PlanContext,
    RunContext,
    RunHandle,
)
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
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
        db=db,
        model=ModelAccess(llm=llm, config=config),
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
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            db=db,
            model=ModelAccess(llm=llm, config=config),
        )

    assert context.project_metadata.language_target == "Unknown Environment"


def test_run_context_isolation_fields_default(tmp_path: Path) -> None:
    """INT-US-09 T5: execution_root defaults to None (callers fall back to project_path);
    enforce_isolation defaults to False (opt-in policy off).

    Both now live on the nested `isolation` object. The behaviour asserted here is unchanged;
    only the path to it is.
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
    """The five worktree-isolation fields, moved off `RunContext` into one frozen object that
    also rejects unknown keyword arguments."""

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
    """The two plan documents, moved into one frozen object.

    The rule that they are DIFFERENT things and must not be merged is unchanged by the move —
    it is now carried by the object's shape and pinned by the tests below."""

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


class TestModelAccess:
    """How a run reaches a language model: adapter, settings, and per-task router."""

    def test_defaults_match_the_previous_flat_defaults(self) -> None:
        access = ModelAccess()
        assert access.llm is None
        assert access.config is None
        assert access.llm_router is None

    def test_run_context_gets_a_default_model_access(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        assert isinstance(context.model, ModelAccess)

    def test_model_is_a_usable_pydantic_field_name(self, tmp_path: Path) -> None:
        """Pydantic v2 reserves the `model_` PREFIX, not the bare word `model`. Verified
        directly rather than assumed, because a silent namespace clash here would surface as
        a confusing failure far from this file."""
        context = RunContext(
            project_path=tmp_path, spec_path=tmp_path / "spec.md", model=ModelAccess(llm="x")
        )
        assert context.model.llm == "x"
        assert context.model_dump()["model"]["llm"] == "x"

    def test_direct_field_mutation_raises(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        with pytest.raises(ValidationError):
            context.model.llm = "x"

    def test_unknown_kwarg_raises(self) -> None:
        with pytest.raises(ValidationError):
            ModelAccess(bogus=1)

    def test_old_flat_paths_are_gone(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        for gone in ("llm", "config", "llm_router"):
            with pytest.raises(AttributeError):
                getattr(context, gone)
            with pytest.raises(ValidationError):
                RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", **{gone: 1})


class TestRunHandle:
    """Who the run is: id, runner, and owning task, all stamped on by the runner."""

    def test_defaults_match_the_previous_flat_defaults(self) -> None:
        handle = RunHandle()
        assert handle.run_id is None
        assert handle.pipeline_runner is None
        assert handle.task_id is None

    def test_re_stamping_the_run_id_preserves_the_pipeline_runner(self, tmp_path: Path) -> None:
        """The runner re-stamps `run_id` every step iteration. FR-11 keeps `pipeline_runner`'s
        fan-out access working, so a partial update must not drop the runner reference."""
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        sentinel = object()
        context.run = context.run.model_copy(update={"pipeline_runner": sentinel})

        context.run = context.run.model_copy(update={"run_id": "run-2"})

        assert context.run.run_id == "run-2"
        assert context.run.pipeline_runner is sentinel

    def test_direct_field_mutation_raises(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        with pytest.raises(ValidationError):
            context.run.run_id = "x"

    def test_unknown_kwarg_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunHandle(bogus=1)

    def test_old_flat_paths_are_gone(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        for gone in ("run_id", "pipeline_runner", "task_id"):
            with pytest.raises(AttributeError):
                getattr(context, gone)


class TestAnalysisContext:
    """The injected code-analysis tools: an analyzer factory and the AST parsers."""

    def test_analyzer_factory_defaults_to_none(self) -> None:
        assert AnalysisContext().analyzer_factory is None

    def test_parsers_are_default_injected_on_construction(self, tmp_path: Path) -> None:
        """`model_post_init` injects the default parser set when none was supplied. The
        behaviour is unchanged by the move; only its destination is now `analysis.parsers`."""
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        assert context.analysis.parsers is not None

    def test_explicitly_supplied_parsers_are_not_overwritten(self, tmp_path: Path) -> None:
        sentinel = {"py": object()}
        context = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            analysis=AnalysisContext(parsers=sentinel),
        )
        assert context.analysis.parsers is sentinel

    def test_parser_loading_failure_degrades_gracefully(self, tmp_path: Path) -> None:
        """[Graceful degradation] Parser loading is best-effort — an import-time explosion
        must leave `parsers` None rather than making RunContext unconstructible."""
        with patch(
            "specweaver.workspace.ast.parsers.factory.get_default_parsers",
            side_effect=RuntimeError("boom"),
        ):
            context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")

        assert context.analysis.parsers is None

    def test_direct_field_mutation_raises(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        with pytest.raises(ValidationError):
            context.analysis.analyzer_factory = object()

    def test_unknown_kwarg_raises(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisContext(bogus=1)

    def test_old_flat_paths_are_gone(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        for gone in ("analyzer_factory", "parsers"):
            with pytest.raises(AttributeError):
                getattr(context, gone)


class TestGraphContext:
    """What the run knows about the project's dependency graph."""

    # --- [Happy Path] ------------------------------------------------------

    def test_defaults_are_all_none(self) -> None:
        graph = GraphContext()
        assert graph.topology is None
        assert graph.stale_nodes is None
        assert graph.workspace_roots is None
        assert graph.api_contract_paths is None

    def test_run_context_gets_a_default_graph_context(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        assert isinstance(context.graph, GraphContext)

    # --- [Boundary] --------------------------------------------------------

    @pytest.mark.parametrize(
        ("existing", "expected"),
        [
            (None, ["new.py"]),
            ([], ["new.py"]),
            (["a.py"], ["a.py", "new.py"]),
            (["a.py", "b.py"], ["a.py", "b.py", "new.py"]),
        ],
    )
    def test_appending_a_contract_path_builds_a_new_list(
        self, tmp_path: Path, existing: list[str] | None, expected: list[str]
    ) -> None:
        """Generation appends to this list as it writes API contracts. The object is frozen,
        so an append has to become a read-build-replace. Covers the empty and unset starting
        points, because those are the ones where a naive rewrite silently drops the value."""
        context = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            graph=GraphContext(api_contract_paths=existing),
        )

        context.graph = context.graph.model_copy(
            update={"api_contract_paths": [*(context.graph.api_contract_paths or []), "new.py"]}
        )

        assert context.graph.api_contract_paths == expected

    def test_replacing_one_field_leaves_the_others(self, tmp_path: Path) -> None:
        original = GraphContext(topology="topo", stale_nodes={"a"}, workspace_roots=["src"])

        updated = original.model_copy(update={"api_contract_paths": ["x.py"]})

        assert updated.topology == "topo"
        assert updated.stale_nodes == {"a"}
        assert updated.workspace_roots == ["src"]

    # --- [Hostile / Wrong Input] ------------------------------------------

    def test_direct_field_mutation_raises(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        with pytest.raises(ValidationError):
            context.graph.topology = "x"

    def test_unknown_kwarg_raises(self) -> None:
        with pytest.raises(ValidationError):
            GraphContext(bogus=1)

    def test_old_flat_paths_are_gone(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        for gone in ("topology", "stale_nodes", "workspace_roots", "api_contract_paths"):
            with pytest.raises(AttributeError):
                getattr(context, gone)
            with pytest.raises(ValidationError):
                RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", **{gone: None})


class TestGuidanceContent:
    """The constitution and coding standards, pasted into prompts."""

    def test_defaults_are_none(self) -> None:
        guidance = GuidanceContent()
        assert guidance.constitution is None
        assert guidance.standards is None

    def test_they_are_supplied_together(self, tmp_path: Path) -> None:
        """Every place that builds a context sets both, which is why they share an object."""
        context = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            guidance=GuidanceContent(constitution="rules", standards="style"),
        )
        assert context.guidance.constitution == "rules"
        assert context.guidance.standards == "style"

    def test_direct_field_mutation_raises(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        with pytest.raises(ValidationError):
            context.guidance.constitution = "x"

    def test_unknown_kwarg_raises(self) -> None:
        with pytest.raises(ValidationError):
            GuidanceContent(bogus=1)

    def test_old_flat_paths_are_gone(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        for gone in ("constitution", "standards"):
            with pytest.raises(AttributeError):
                getattr(context, gone)
            with pytest.raises(ValidationError):
                RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", **{gone: "x"})


class TestRemovedFields:
    """Two fields are gone, for different reasons, and passing either is now an error rather
    than a value that silently disappears.

    `env_vars` was never wired to anything: the plan was to inject it into spawned processes
    and that half was never built, and bash steps later got an explicit per-step `env:` map
    instead, which deliberately does NOT read this field so secrets cannot leak into it.

    `pipeline_name` was read in two places but never set anywhere, so both reads always took
    their fallback. Both now take the name from the run itself, which fixed a real bug -- see
    the reserve-gate tests.
    """

    @pytest.mark.parametrize(
        ("field", "value"), [("env_vars", {"A": "1"}), ("pipeline_name", "flow")]
    )
    def test_removed_field_is_rejected_and_absent(
        self, tmp_path: Path, field: str, value: object
    ) -> None:
        with pytest.raises(ValidationError):
            RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", **{field: value})

        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        with pytest.raises(AttributeError):
            getattr(context, field)


class TestConstructionHelpers:
    """`model_post_init` was long enough to hide what it did. Its two jobs are now named
    methods that can be exercised on their own."""

    def test_default_parsers_needs_no_context_at_all(self) -> None:
        """A plain function of nothing, so it can be tested without building a context."""
        assert RunContext._default_parsers() is not None

    def test_default_parsers_swallows_a_loading_failure(self) -> None:
        """Parser loading is best-effort: most steps never touch one, so a failure here must
        not make every context in the process unconstructible."""
        with patch(
            "specweaver.workspace.ast.parsers.factory.get_default_parsers",
            side_effect=RuntimeError("boom"),
        ):
            assert RunContext._default_parsers() is None

    def test_build_project_metadata_reads_the_project(self, tmp_path: Path) -> None:
        (tmp_path / "context.yaml").write_text("archetype: web-service\n", encoding="utf-8")
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")

        metadata = context._build_project_metadata()

        assert metadata.project_name == tmp_path.name
        assert metadata.archetype == "web-service"

    def test_build_project_metadata_falls_back_without_a_context_file(self, tmp_path: Path) -> None:
        context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")

        assert context._build_project_metadata().archetype == "generic"
