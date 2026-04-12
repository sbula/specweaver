# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for planning models — PlanArtifact and supporting models."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from specweaver.workflows.planning.models import (
    KNOWN_ARCHETYPES,
    ArchitectureSection,
    ConstraintNote,
    FileChange,
    ImplementationTask,
    MethodSignature,
    MockupReference,
    PlanArtifact,
    TechStackChoice,
    TestExpectation,
)

# ---------------------------------------------------------------------------
# FileChange
# ---------------------------------------------------------------------------


class TestFileChange:
    """FileChange describes a single file to create or modify."""

    def test_minimal_construction(self) -> None:
        f = FileChange(
            path="src/auth/login.py",
            action="create",
            purpose="Authentication login handler",
        )
        assert f.path == "src/auth/login.py"
        assert f.action == "create"
        assert f.purpose == "Authentication login handler"

    def test_valid_actions(self) -> None:
        """All three valid action values work."""
        for action in ("create", "modify", "delete"):
            f = FileChange(path="test.py", action=action, purpose="test")
            assert f.action == action

    def test_invalid_action_rejected(self) -> None:
        """Invalid action values are rejected by Literal validation."""
        with pytest.raises(ValidationError):
            FileChange(path="test.py", action="rename", purpose="test")

    def test_dependencies_default_empty(self) -> None:
        f = FileChange(path="test.py", action="create", purpose="test")
        assert f.dependencies == []

    def test_dependencies_can_be_set(self) -> None:
        f = FileChange(
            path="src/auth/tokens.py",
            action="create",
            purpose="Token generation",
            dependencies=["src/auth/login.py"],
        )
        assert f.dependencies == ["src/auth/login.py"]

    def test_serialization_round_trip(self) -> None:
        f = FileChange(
            path="src/billing/invoice.py",
            action="modify",
            purpose="Add tax calculation",
            dependencies=["src/billing/tax.py"],
        )
        data = f.model_dump()
        f2 = FileChange.model_validate(data)
        assert f2.path == "src/billing/invoice.py"
        assert f2.dependencies == ["src/billing/tax.py"]


# ---------------------------------------------------------------------------
# ArchitectureSection
# ---------------------------------------------------------------------------


class TestArchitectureSection:
    """ArchitectureSection describes architecture decisions."""

    def test_minimal_construction(self) -> None:
        a = ArchitectureSection(
            module_layout="Single module with service layer",
            dependency_direction="top-down",
            archetype="adapter",
        )
        assert a.module_layout == "Single module with service layer"
        assert a.archetype == "adapter"

    def test_patterns_default_empty(self) -> None:
        a = ArchitectureSection(
            module_layout="flat",
            dependency_direction="inward",
            archetype="orchestrator",
        )
        assert a.patterns == []

    def test_known_archetypes_accepted(self) -> None:
        """All known archetypes work without issue."""
        for archetype in KNOWN_ARCHETYPES:
            a = ArchitectureSection(
                module_layout="test",
                dependency_direction="test",
                archetype=archetype,
            )
            assert a.archetype == archetype

    def test_unknown_archetype_accepted(self) -> None:
        """Unknown archetypes are accepted (free-form string, warning only)."""
        a = ArchitectureSection(
            module_layout="test",
            dependency_direction="test",
            archetype="saga-pattern",
        )
        assert a.archetype == "saga-pattern"

    def test_serialization_round_trip(self) -> None:
        a = ArchitectureSection(
            module_layout="Hexagonal",
            dependency_direction="inward",
            archetype="adapter",
            patterns=["repository", "factory"],
        )
        data = a.model_dump()
        a2 = ArchitectureSection.model_validate(data)
        assert a2.patterns == ["repository", "factory"]


# ---------------------------------------------------------------------------
# TechStackChoice
# ---------------------------------------------------------------------------


class TestTechStackChoice:
    """TechStackChoice records a technology choice with rationale."""

    def test_construction(self) -> None:
        t = TechStackChoice(
            category="testing framework",
            choice="pytest",
            rationale="Standard Python testing framework",
        )
        assert t.category == "testing framework"
        assert t.choice == "pytest"

    def test_alternatives_default_empty(self) -> None:
        t = TechStackChoice(
            category="http client",
            choice="httpx",
            rationale="Async support",
        )
        assert t.alternatives_considered == []

    def test_serialization_round_trip(self) -> None:
        t = TechStackChoice(
            category="ORM",
            choice="SQLAlchemy",
            rationale="Mature, async support",
            alternatives_considered=["Tortoise", "SQLModel"],
        )
        data = t.model_dump()
        t2 = TechStackChoice.model_validate(data)
        assert t2.alternatives_considered == ["Tortoise", "SQLModel"]


# ---------------------------------------------------------------------------
# ConstraintNote
# ---------------------------------------------------------------------------


class TestConstraintNote:
    """ConstraintNote captures a constraint from the spec."""

    def test_construction(self) -> None:
        c = ConstraintNote(
            source="§ Boundaries",
            constraint="Must not exceed 100ms response time",
            impact="Requires caching layer",
        )
        assert c.source == "§ Boundaries"
        assert c.constraint == "Must not exceed 100ms response time"

    def test_serialization_round_trip(self) -> None:
        c = ConstraintNote(
            source="§ Policy",
            constraint="Max 3 retries",
            impact="Need exponential backoff",
        )
        data = c.model_dump()
        c2 = ConstraintNote.model_validate(data)
        assert c2.source == "§ Policy"


# ---------------------------------------------------------------------------
# MethodSignature
# ---------------------------------------------------------------------------


class TestMethodSignature:
    """MethodSignature represents an expected AST function signature."""

    def test_construction(self) -> None:
        m = MethodSignature(
            name="detect_drift",
            parameters=["ast: tree_sitter.Tree", "plan: PlanArtifact"],
            return_type="DriftReport",
        )
        assert m.name == "detect_drift"
        assert m.parameters == ["ast: tree_sitter.Tree", "plan: PlanArtifact"]
        assert m.return_type == "DriftReport"

    def test_serialization_round_trip(self) -> None:
        m = MethodSignature(
            name="get_users",
            parameters=[],
            return_type="list[User]",
        )
        data = m.model_dump()
        m2 = MethodSignature.model_validate(data)
        assert m2.return_type == "list[User]"


# ---------------------------------------------------------------------------
# ImplementationTask
# ---------------------------------------------------------------------------


class TestImplementationTask:
    """ImplementationTask defines an ordered implementation step."""

    def test_minimal_construction(self) -> None:
        t = ImplementationTask(
            sequence_number=1,
            name="Create auth module",
            description="Set up authentication module skeleton",
            files=["src/auth/__init__.py", "src/auth/login.py"],
        )
        assert t.name == "Create auth module"
        assert t.sequence_number == 1
        assert len(t.files) == 2
        assert t.expected_signatures == {}

    def test_sequence_number_default(self) -> None:
        """Legacy JSON defaults sequence_number to 0."""
        t = ImplementationTask(
            name="Legacy block",
            description="Has no sequence number",
            files=[],
        )
        assert t.sequence_number == 0

    def test_dependencies_default_empty(self) -> None:
        t = ImplementationTask(
            name="test",
            description="test",
            files=[],
        )
        assert t.dependencies == []

    def test_serialization_round_trip(self) -> None:
        t = ImplementationTask(
            name="Implement login",
            description="Build login endpoint",
            files=["src/auth/login.py"],
            dependencies=["Create auth module"],
        )
        data = t.model_dump()
        t2 = ImplementationTask.model_validate(data)
        assert t2.dependencies == ["Create auth module"]


# ---------------------------------------------------------------------------
# TestExpectation
# ---------------------------------------------------------------------------


class TestTestExpectation:
    """TestExpectation defines a lightweight test scenario hint."""

    def test_construction(self) -> None:
        te = TestExpectation(
            name="happy_path_login",
            description="Valid credentials return a token",
            function_under_test="authenticate()",
            input_summary="valid email + password",
            expected_behavior="returns JWT token",
        )
        assert te.name == "happy_path_login"
        assert te.category == "happy"  # default

    def test_valid_categories(self) -> None:
        """All three categories work."""
        for cat in ("happy", "error", "boundary"):
            te = TestExpectation(
                name="test",
                description="test",
                function_under_test="f()",
                input_summary="x",
                expected_behavior="y",
                category=cat,
            )
            assert te.category == cat

    def test_invalid_category_rejected(self) -> None:
        """Invalid category values are rejected by Literal validation."""
        with pytest.raises(ValidationError):
            TestExpectation(
                name="test",
                description="test",
                function_under_test="f()",
                input_summary="x",
                expected_behavior="y",
                category="performance",
            )

    def test_serialization_round_trip(self) -> None:
        te = TestExpectation(
            name="error_invalid_credentials",
            description="Invalid password raises AuthError",
            function_under_test="authenticate()",
            input_summary="wrong password",
            expected_behavior="raises AuthError",
            category="error",
        )
        data = te.model_dump()
        te2 = TestExpectation.model_validate(data)
        assert te2.category == "error"


# ---------------------------------------------------------------------------
# MockupReference
# ---------------------------------------------------------------------------


class TestMockupReference:
    """MockupReference stores Stitch preview URL for a UI screen."""

    def test_construction(self) -> None:
        m = MockupReference(
            screen_name="Login Page",
            description="OAuth2 login form",
            preview_url="https://stitch.withgoogle.com/preview/abc123",
        )
        assert m.screen_name == "Login Page"
        assert m.preview_url.startswith("https://")


# ---------------------------------------------------------------------------
# PlanArtifact
# ---------------------------------------------------------------------------


class TestPlanArtifact:
    """PlanArtifact is the complete implementation plan for a spec."""

    @pytest.fixture()
    def sample_plan(self) -> PlanArtifact:
        return PlanArtifact(
            spec_path="specs/login_spec.md",
            spec_name="Login Component",
            spec_hash="abc123def456",
            file_layout=[
                FileChange(
                    path="src/auth/login.py",
                    action="create",
                    purpose="Login handler",
                ),
                FileChange(
                    path="src/auth/tokens.py",
                    action="create",
                    purpose="JWT token generation",
                    dependencies=["src/auth/login.py"],
                ),
            ],
            timestamp="2026-03-22T10:00:00Z",
            architecture=ArchitectureSection(
                module_layout="auth/ module with service pattern",
                dependency_direction="downward",
                archetype="adapter",
                patterns=["strategy"],
            ),
            tech_stack=[
                TechStackChoice(
                    category="JWT library",
                    choice="PyJWT",
                    rationale="Lightweight, well-maintained",
                    alternatives_considered=["python-jose"],
                ),
            ],
            constraints=[
                ConstraintNote(
                    source="§ Boundaries",
                    constraint="Token expiry <= 1h",
                    impact="Short-lived tokens, need refresh flow",
                ),
            ],
            tasks=[
                ImplementationTask(
                    name="Create auth module",
                    description="Scaffold auth/ directory",
                    files=["src/auth/__init__.py"],
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
            reasoning="The auth module should use adapter pattern for provider flexibility.",
            confidence=85,
        )

    def test_mandatory_fields(self, sample_plan: PlanArtifact) -> None:
        assert sample_plan.spec_path == "specs/login_spec.md"
        assert sample_plan.spec_name == "Login Component"
        assert sample_plan.spec_hash == "abc123def456"
        assert len(sample_plan.file_layout) == 2
        assert sample_plan.timestamp == "2026-03-22T10:00:00Z"

    def test_optional_fields_populated(self, sample_plan: PlanArtifact) -> None:
        assert sample_plan.architecture is not None
        assert len(sample_plan.tech_stack) == 1
        assert len(sample_plan.constraints) == 1
        assert len(sample_plan.tasks) == 1
        assert len(sample_plan.test_expectations) == 1
        assert sample_plan.reasoning != ""
        assert sample_plan.confidence == 85

    def test_minimal_valid_plan(self) -> None:
        """Plan with only mandatory fields is valid."""
        plan = PlanArtifact(
            spec_path="specs/util.md",
            spec_name="Utility",
            spec_hash="deadbeef",
            file_layout=[
                FileChange(path="src/util.py", action="create", purpose="Helper functions"),
            ],
            timestamp="2026-03-22T00:00:00Z",
        )
        assert plan.architecture is None
        assert plan.tech_stack == []
        assert plan.constraints == []
        assert plan.tasks == []
        assert plan.test_expectations == []
        assert plan.mockups == []
        assert plan.reasoning == ""
        assert plan.confidence == 0

    def test_empty_file_layout_accepted(self) -> None:
        """Plan with no files is technically valid (maybe advisory only)."""
        plan = PlanArtifact(
            spec_path="specs/review.md",
            spec_name="Review",
            spec_hash="aabbcc",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
        )
        assert len(plan.file_layout) == 0

    def test_json_round_trip(self, sample_plan: PlanArtifact) -> None:
        """Plan survives JSON serialization round-trip."""
        json_str = sample_plan.model_dump_json()
        parsed = json.loads(json_str)
        plan2 = PlanArtifact.model_validate(parsed)
        assert plan2.spec_path == "specs/login_spec.md"
        assert len(plan2.file_layout) == 2
        assert plan2.architecture is not None
        assert plan2.architecture.archetype == "adapter"
        assert plan2.confidence == 85

    def test_dict_round_trip(self, sample_plan: PlanArtifact) -> None:
        """Plan survives model_dump → model_validate round-trip."""
        data = sample_plan.model_dump()
        plan2 = PlanArtifact.model_validate(data)
        assert plan2.spec_name == sample_plan.spec_name
        assert len(plan2.file_layout) == 2
        assert plan2.file_layout[1].dependencies == ["src/auth/login.py"]

    def test_file_layout_count(self, sample_plan: PlanArtifact) -> None:
        """file_layout count is accessible for file-count warnings."""
        assert len(sample_plan.file_layout) == 2

    def test_confidence_range_not_enforced(self) -> None:
        """Confidence outside 0-100 is accepted (LLM may produce any int)."""
        plan = PlanArtifact(
            spec_path="test.md",
            spec_name="test",
            spec_hash="x",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
            confidence=150,
        )
        assert plan.confidence == 150

    def test_missing_mandatory_field_raises(self) -> None:
        """Missing spec_path raises ValidationError."""
        with pytest.raises(ValidationError):
            PlanArtifact(
                spec_name="test",
                spec_hash="x",
                file_layout=[],
                timestamp="2026-03-22T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestPlanArtifactEdgeCases:
    """Edge cases for planning models."""

    def test_known_archetypes_set(self) -> None:
        """KNOWN_ARCHETYPES is a complete set."""
        assert {"adapter", "orchestrator", "pure-logic", "leaf", "data"} == KNOWN_ARCHETYPES

    def test_archetype_not_in_known_still_works(self) -> None:
        """Unknown archetype in a full plan doesn't break anything."""
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
        assert plan.architecture is not None
        assert plan.architecture.archetype == "event-sourcing"
        assert plan.architecture.archetype not in KNOWN_ARCHETYPES

    def test_mockups_populated(self) -> None:
        """Mockups can be populated (3.6b readiness)."""
        plan = PlanArtifact(
            spec_path="test.md",
            spec_name="test",
            spec_hash="x",
            file_layout=[],
            timestamp="2026-03-22T00:00:00Z",
            mockups=[
                MockupReference(
                    screen_name="Dashboard",
                    description="Main dashboard",
                    preview_url="https://stitch.dev/preview/123",
                ),
            ],
        )
        assert len(plan.mockups) == 1
        assert plan.mockups[0].screen_name == "Dashboard"

    def test_large_file_layout(self) -> None:
        """Plan with many files works (tests file count warning threshold)."""
        files = [
            FileChange(path=f"src/module_{i}.py", action="create", purpose=f"Module {i}")
            for i in range(20)
        ]
        plan = PlanArtifact(
            spec_path="test.md",
            spec_name="test",
            spec_hash="x",
            file_layout=files,
            timestamp="2026-03-22T00:00:00Z",
        )
        assert len(plan.file_layout) == 20
