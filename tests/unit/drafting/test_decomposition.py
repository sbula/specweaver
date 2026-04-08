# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for decomposition models — ComponentChange, IntegrationSeam, DecompositionPlan."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from specweaver.commons.enums.dal import DALLevel
from specweaver.drafting.decomposition import (
    ComponentChange,
    DecompositionPlan,
    IntegrationSeam,
)

# ---------------------------------------------------------------------------
# ComponentChange
# ---------------------------------------------------------------------------


class TestComponentChange:
    """ComponentChange describes a single component affected by a feature."""

    def test_minimal_construction(self) -> None:
        c = ComponentChange(
            component="billing_service",
            exists=True,
            change_nature="behavior",
            description="Add tax calculation endpoint",
            proposed_dal="DAL_E",
        )
        assert c.component == "billing_service"
        assert c.exists is True
        assert c.change_nature == "behavior"

    def test_dependencies_default_empty(self) -> None:
        c = ComponentChange(
            component="auth",
            exists=True,
            change_nature="config",
            description="Add mTLS config",
            proposed_dal="DAL_E",
        )
        assert c.dependencies == []

    def test_confidence_default_zero(self) -> None:
        c = ComponentChange(
            component="auth",
            exists=True,
            change_nature="config",
            description="test",
            proposed_dal="DAL_E",
        )
        assert c.confidence == 0

    def test_confidence_can_be_set(self) -> None:
        c = ComponentChange(
            component="auth",
            exists=True,
            change_nature="config",
            description="test",
            proposed_dal="DAL_E",
            confidence=85,
        )
        assert c.confidence == 85

    def test_valid_change_natures(self) -> None:
        """All four valid change_nature values work."""
        for nature in ("new_interface", "schema", "behavior", "config"):
            c = ComponentChange(
                component="test",
                exists=True,
                change_nature=nature,
                description="test",
                proposed_dal="DAL_E",
            )
            assert c.change_nature == nature

    def test_serialization_round_trip(self) -> None:
        c = ComponentChange(
            component="billing",
            exists=False,
            change_nature="new_interface",
            description="New billing API",
            proposed_dal="DAL_E",
            dependencies=["auth", "orders"],
            confidence=90,
        )
        data = c.model_dump()
        c2 = ComponentChange.model_validate(data)
        assert c2.component == "billing"
        assert c2.dependencies == ["auth", "orders"]
        assert c2.confidence == 90

    def test_proposed_dal_rejects_hallucinations(self) -> None:
        """Pydantic structurally rejects invalid DAL Enums (e.g., 'DAL_Z')."""
        with pytest.raises(ValidationError) as exc_info:
            ComponentChange(
                component="test",
                exists=True,
                change_nature="behavior",
                description="test",
                proposed_dal="DAL_Z",  # type: ignore
            )
        assert "Input should be" in str(exc_info.value)

    def test_proposed_dal_parses_valid_strings(self) -> None:
        """Pydantic successfully parses valid strings into DALLevel Enum."""
        c = ComponentChange(
            component="test",
            exists=True,
            change_nature="behavior",
            description="test",
            proposed_dal="DAL_C",  # type: ignore
        )
        assert c.proposed_dal is DALLevel.DAL_C

    def test_json_pipeline_parsing(self) -> None:
        """Integration: DecompositionPlan parses string Enums natively."""
        raw_json = """{
            "feature_spec": "test.md",
            "components": [{
                "component": "auth",
                "exists": true,
                "change_nature": "behavior",
                "description": "test",
                "proposed_dal": "DAL_B"
            }],
            "integration_seams": [],
            "build_sequence": ["auth"],
            "coverage_score": 0.9,
            "alignment_notes": [],
            "timestamp": "2026-04-05T08:00:00Z"
        }"""
        plan = DecompositionPlan.model_validate_json(raw_json)
        assert plan.components[0].proposed_dal is DALLevel.DAL_B


# ---------------------------------------------------------------------------
# IntegrationSeam
# ---------------------------------------------------------------------------


class TestIntegrationSeam:
    """IntegrationSeam describes a connection between two components."""

    def test_construction(self) -> None:
        s = IntegrationSeam(
            between=("billing", "orders"),
            contract="OrderPlaced event",
            format="event",
        )
        assert s.between == ("billing", "orders")
        assert s.contract == "OrderPlaced event"
        assert s.format == "event"

    def test_confidence_default_zero(self) -> None:
        s = IntegrationSeam(
            between=("a", "b"),
            contract="test",
            format="API call",
        )
        assert s.confidence == 0

    def test_confidence_can_be_set(self) -> None:
        s = IntegrationSeam(
            between=("a", "b"),
            contract="test",
            format="shared type",
            confidence=75,
        )
        assert s.confidence == 75

    def test_serialization_round_trip(self) -> None:
        s = IntegrationSeam(
            between=("billing", "auth"),
            contract="JWT token",
            format="shared type",
            confidence=88,
        )
        data = s.model_dump()
        s2 = IntegrationSeam.model_validate(data)
        assert s2.between == ("billing", "auth")
        assert s2.confidence == 88


# ---------------------------------------------------------------------------
# DecompositionPlan
# ---------------------------------------------------------------------------


class TestDecompositionPlan:
    """DecompositionPlan is the output of the decomposition step."""

    @pytest.fixture()
    def sample_plan(self) -> DecompositionPlan:
        return DecompositionPlan(
            feature_spec="specs/sell_shares_feature_spec.md",
            components=[
                ComponentChange(
                    component="order_service",
                    exists=True,
                    change_nature="behavior",
                    description="Add sell order logic",
                    proposed_dal="DAL_E",
                    confidence=92,
                ),
                ComponentChange(
                    component="settlement",
                    exists=False,
                    change_nature="new_interface",
                    description="New settlement module",
                    proposed_dal="DAL_E",
                    dependencies=["order_service"],
                    confidence=78,
                ),
            ],
            integration_seams=[
                IntegrationSeam(
                    between=("order_service", "settlement"),
                    contract="SellOrderPlaced event",
                    format="event",
                    confidence=85,
                ),
            ],
            build_sequence=["order_service", "settlement"],
            coverage_score=0.85,
            alignment_notes=["New settlement module not in existing topology"],
            timestamp="2026-03-18T05:00:00Z",
        )

    def test_feature_spec_path(self, sample_plan: DecompositionPlan) -> None:
        assert sample_plan.feature_spec == "specs/sell_shares_feature_spec.md"

    def test_components_count(self, sample_plan: DecompositionPlan) -> None:
        assert len(sample_plan.components) == 2

    def test_integration_seams_count(self, sample_plan: DecompositionPlan) -> None:
        assert len(sample_plan.integration_seams) == 1

    def test_build_sequence(self, sample_plan: DecompositionPlan) -> None:
        assert sample_plan.build_sequence == ["order_service", "settlement"]

    def test_coverage_score(self, sample_plan: DecompositionPlan) -> None:
        assert sample_plan.coverage_score == 0.85

    def test_alignment_notes(self, sample_plan: DecompositionPlan) -> None:
        assert len(sample_plan.alignment_notes) == 1

    def test_json_round_trip(self, sample_plan: DecompositionPlan) -> None:
        """Plan survives JSON serialization round-trip."""
        json_str = sample_plan.model_dump_json()
        parsed = json.loads(json_str)
        plan2 = DecompositionPlan.model_validate(parsed)
        assert plan2.coverage_score == 0.85
        assert len(plan2.components) == 2
        assert plan2.components[0].confidence == 92

    def test_dict_round_trip(self, sample_plan: DecompositionPlan) -> None:
        """Plan survives model_dump → model_validate round-trip."""
        data = sample_plan.model_dump()
        plan2 = DecompositionPlan.model_validate(data)
        assert plan2.feature_spec == sample_plan.feature_spec
        assert len(plan2.components) == 2
        assert plan2.components[0].confidence == 92

    def test_empty_plan(self) -> None:
        """An empty plan is valid (greenfield with no changes yet)."""
        plan = DecompositionPlan(
            feature_spec="specs/empty.md",
            components=[],
            integration_seams=[],
            build_sequence=[],
            coverage_score=0.0,
            alignment_notes=[],
            timestamp="2026-03-18T00:00:00Z",
        )
        assert len(plan.components) == 0
        assert plan.coverage_score == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestDecompositionEdgeCases:
    """Edge cases for decomposition models."""

    def test_coverage_score_above_one_accepted(self) -> None:
        """coverage_score > 1.0 is silently accepted (no validator)."""
        plan = DecompositionPlan(
            feature_spec="test.md",
            components=[],
            integration_seams=[],
            build_sequence=[],
            coverage_score=1.5,
            timestamp="2026-03-18T00:00:00Z",
        )
        assert plan.coverage_score == 1.5

    def test_coverage_score_negative_accepted(self) -> None:
        """coverage_score < 0 is silently accepted (no validator)."""
        plan = DecompositionPlan(
            feature_spec="test.md",
            components=[],
            integration_seams=[],
            build_sequence=[],
            coverage_score=-0.5,
            timestamp="2026-03-18T00:00:00Z",
        )
        assert plan.coverage_score == -0.5

    def test_between_tuple_order_matters(self) -> None:
        """('a','b') and ('b','a') are different seams — no normalization."""
        s1 = IntegrationSeam(between=("a", "b"), contract="c", format="event")
        s2 = IntegrationSeam(between=("b", "a"), contract="c", format="event")
        assert s1.between != s2.between

    def test_arbitrary_change_nature_accepted(self) -> None:
        """change_nature is a plain str — any value is accepted."""
        c = ComponentChange(
            component="test",
            exists=True,
            change_nature="refactor",  # not in the documented 4 values
            description="Refactoring",
            proposed_dal="DAL_E",
        )
        assert c.change_nature == "refactor"

    def test_confidence_negative_accepted(self) -> None:
        """Negative confidence is accepted (no validator)."""
        c = ComponentChange(
            component="test",
            exists=True,
            change_nature="behavior",
            description="test",
            proposed_dal="DAL_E",
            confidence=-10,
        )
        assert c.confidence == -10

    def test_confidence_over_100_accepted(self) -> None:
        """Confidence > 100 is accepted (no validator)."""
        s = IntegrationSeam(
            between=("a", "b"),
            contract="c",
            format="event",
            confidence=200,
        )
        assert s.confidence == 200
