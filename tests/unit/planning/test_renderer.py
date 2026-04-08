# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for planning renderer — Markdown rendering from PlanArtifact."""

from __future__ import annotations

import pytest

from specweaver.planning.models import (
    ArchitectureSection,
    ConstraintNote,
    FileChange,
    ImplementationTask,
    MockupReference,
    PlanArtifact,
    TechStackChoice,
    TestExpectation,
)
from specweaver.planning.renderer import render_plan_markdown

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def full_plan() -> PlanArtifact:
    """A fully populated plan for rendering tests."""
    return PlanArtifact(
        spec_path="specs/login_spec.md",
        spec_name="Login Component",
        spec_hash="abc123def456789",
        file_layout=[
            FileChange(path="src/auth/login.py", action="create", purpose="Login handler"),
            FileChange(path="src/auth/tokens.py", action="modify", purpose="Add JWT support"),
        ],
        timestamp="2026-03-22T10:00:00Z",
        architecture=ArchitectureSection(
            module_layout="auth/ module with service pattern",
            dependency_direction="downward",
            archetype="adapter",
            patterns=["strategy", "factory"],
        ),
        tech_stack=[
            TechStackChoice(
                category="JWT library",
                choice="PyJWT",
                rationale="Lightweight",
                alternatives_considered=["python-jose"],
            ),
        ],
        constraints=[
            ConstraintNote(
                source="§ Boundaries",
                constraint="Token expiry <= 1h",
                impact="Need refresh flow",
            ),
        ],
        tasks=[
            ImplementationTask(
                name="Create auth module",
                description="Scaffold auth/ directory",
                files=["src/auth/__init__.py"],
            ),
            ImplementationTask(
                name="Implement login",
                description="Build login endpoint",
                files=["src/auth/login.py"],
                dependencies=["Create auth module"],
            ),
        ],
        test_expectations=[
            TestExpectation(
                name="happy_login",
                description="Valid creds return token",
                function_under_test="login()",
                input_summary="valid email+pass",
                expected_behavior="JWT string",
            ),
        ],
        mockups=[
            MockupReference(
                screen_name="Login Page",
                description="OAuth2 login form",
                preview_url="https://stitch.dev/preview/abc123",
            ),
        ],
        reasoning="Adapter pattern for provider flexibility.",
        confidence=85,
    )


@pytest.fixture()
def minimal_plan() -> PlanArtifact:
    """A plan with only mandatory fields."""
    return PlanArtifact(
        spec_path="specs/util.md",
        spec_name="Utility",
        spec_hash="deadbeef",
        file_layout=[
            FileChange(path="src/util.py", action="create", purpose="Helper functions"),
        ],
        timestamp="2026-03-22T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


class TestRenderHeader:
    """Header section of the rendered Markdown."""

    def test_contains_spec_name(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "# Plan: Login Component" in md

    def test_contains_spec_path(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "`specs/login_spec.md`" in md

    def test_contains_confidence(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "85/100" in md

    def test_contains_timestamp(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "2026-03-22T10:00:00Z" in md

    def test_contains_truncated_hash(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "`abc123def456...`" in md


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------


class TestRenderArchitecture:
    """Architecture section rendering."""

    def test_architecture_present(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "## Architecture" in md
        assert "adapter" in md
        assert "downward" in md

    def test_patterns_rendered(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "strategy, factory" in md

    def test_unknown_archetype_warning(self) -> None:
        plan = PlanArtifact(
            spec_path="test.md",
            spec_name="test",
            spec_hash="x",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
            architecture=ArchitectureSection(
                module_layout="custom",
                dependency_direction="lateral",
                archetype="event-sourcing",
            ),
        )
        md = render_plan_markdown(plan)
        assert "⚠️" in md
        assert "unknown archetype" in md

    def test_no_architecture_section_when_none(self, minimal_plan: PlanArtifact) -> None:
        md = render_plan_markdown(minimal_plan)
        assert "## Architecture" not in md


# ---------------------------------------------------------------------------
# File Layout
# ---------------------------------------------------------------------------


class TestRenderFileLayout:
    """File layout section rendering."""

    def test_file_count(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "2 files" in md

    def test_simple_complexity(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "🟢 Simple" in md

    def test_moderate_complexity(self) -> None:
        files = [FileChange(path=f"f{i}.py", action="create", purpose="x") for i in range(10)]
        plan = PlanArtifact(
            spec_path="t.md",
            spec_name="t",
            spec_hash="x",
            file_layout=files,
            timestamp="2026-03-22T00:00:00Z",
        )
        md = render_plan_markdown(plan)
        assert "🟡 Moderate" in md

    def test_high_complexity(self) -> None:
        files = [FileChange(path=f"f{i}.py", action="create", purpose="x") for i in range(20)]
        plan = PlanArtifact(
            spec_path="t.md",
            spec_name="t",
            spec_hash="x",
            file_layout=files,
            timestamp="2026-03-22T00:00:00Z",
        )
        md = render_plan_markdown(plan)
        assert "🔴 Consider splitting" in md

    def test_empty_file_layout(self) -> None:
        plan = PlanArtifact(
            spec_path="t.md",
            spec_name="t",
            spec_hash="x",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
        )
        md = render_plan_markdown(plan)
        assert "No files specified" in md


# ---------------------------------------------------------------------------
# Other sections
# ---------------------------------------------------------------------------


class TestRenderOptionalSections:
    """Optional sections (tech stack, constraints, tasks, etc.)."""

    def test_tech_stack_table(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "## Tech Stack" in md
        assert "PyJWT" in md
        assert "python-jose" in md

    def test_constraints_rendered(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "## Constraints" in md
        assert "Token expiry" in md

    def test_tasks_numbered(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "## Implementation Tasks" in md
        assert "1. **Create auth module**" in md
        assert "2. **Implement login**" in md
        assert "depends on: Create auth module" in md

    def test_test_expectations_table(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "## Test Expectations" in md
        assert "happy_login" in md

    def test_mockups_rendered(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "## UI Mockups" in md
        assert "Login Page" in md
        assert "https://stitch.dev/preview/abc123" in md


# ---------------------------------------------------------------------------
# Reasoning (verbose)
# ---------------------------------------------------------------------------


class TestRenderReasoning:
    """Reasoning section is omitted unless verbose=True."""

    def test_reasoning_hidden_by_default(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan)
        assert "## Reasoning" not in md
        assert "Adapter pattern" not in md

    def test_reasoning_shown_when_verbose(self, full_plan: PlanArtifact) -> None:
        md = render_plan_markdown(full_plan, verbose=True)
        assert "## Reasoning" in md
        assert "Adapter pattern" in md

    def test_no_reasoning_section_when_empty_verbose(self, minimal_plan: PlanArtifact) -> None:
        md = render_plan_markdown(minimal_plan, verbose=True)
        assert "## Reasoning" not in md


# ---------------------------------------------------------------------------
# Minimal plan
# ---------------------------------------------------------------------------


class TestRenderMinimalPlan:
    """Rendering a plan with only mandatory fields."""

    def test_no_optional_sections(self, minimal_plan: PlanArtifact) -> None:
        md = render_plan_markdown(minimal_plan)
        assert "## Architecture" not in md
        assert "## Tech Stack" not in md
        assert "## Constraints" not in md
        assert "## Implementation Tasks" not in md
        assert "## Test Expectations" not in md
        assert "## UI Mockups" not in md

    def test_has_file_layout(self, minimal_plan: PlanArtifact) -> None:
        md = render_plan_markdown(minimal_plan)
        assert "## File Layout" in md
        assert "src/util.py" in md


# ---------------------------------------------------------------------------
# Edge cases for individual sections
# ---------------------------------------------------------------------------


class TestRenderSectionEdgeCases:
    """Edge cases for architecture, tech stack, and tasks rendering."""

    def test_architecture_no_patterns(self) -> None:
        """Architecture with patterns=None should omit the Patterns line."""
        plan = PlanArtifact(
            spec_path="t.md",
            spec_name="t",
            spec_hash="x",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
            architecture=ArchitectureSection(
                module_layout="flat",
                dependency_direction="downward",
                archetype="adapter",
            ),
        )
        md = render_plan_markdown(plan)
        assert "## Architecture" in md
        assert "Patterns" not in md

    def test_tech_stack_no_alternatives(self) -> None:
        """Tech stack choice with no alternatives omits the '(vs. ...)' suffix."""
        plan = PlanArtifact(
            spec_path="t.md",
            spec_name="t",
            spec_hash="x",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
            tech_stack=[
                TechStackChoice(
                    category="ORM",
                    choice="SQLAlchemy",
                    rationale="Industry standard",
                    alternatives_considered=[],
                ),
            ],
        )
        md = render_plan_markdown(plan)
        assert "## Tech Stack" in md
        assert "SQLAlchemy" in md
        assert "vs." not in md

    def test_task_with_no_files(self) -> None:
        """Task without files should not render a Files: line."""
        plan = PlanArtifact(
            spec_path="t.md",
            spec_name="t",
            spec_hash="x",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
            tasks=[
                ImplementationTask(
                    name="Research",
                    description="Read docs",
                    files=[],
                ),
            ],
        )
        md = render_plan_markdown(plan)
        assert "## Implementation Tasks" in md
        assert "Research" in md
        assert "Files:" not in md

    def test_task_with_no_dependencies(self) -> None:
        """Task without dependencies should not render a dependencies suffix."""
        plan = PlanArtifact(
            spec_path="t.md",
            spec_name="t",
            spec_hash="x",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
            tasks=[
                ImplementationTask(
                    name="Setup",
                    description="Init project",
                    files=[],
                ),
            ],
        )
        md = render_plan_markdown(plan)
        assert "## Implementation Tasks" in md
        assert "Setup" in md
        assert "depends on" not in md
