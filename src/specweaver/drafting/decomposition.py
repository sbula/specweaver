# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Decomposition models — structured output for the decompose step.

These Pydantic models define the machine-readable output of the
decomposition agent:
- ``ComponentChange``: a single component affected by a feature.
- ``IntegrationSeam``: a connection between two affected components.
- ``DecompositionPlan``: the full decomposition result with
  ``coverage_score`` and ``alignment_notes`` for future auto-gates.

Every item carries a ``confidence`` score (0-100) from the LLM,
enabling threshold-based filtering and structured decision criteria.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from specweaver.commons.enums.dal import DALLevel  # noqa: TC001


class ComponentChange(BaseModel):
    """A single component affected by a feature.

    Attributes:
        component: Service/module name.
        exists: True = modify existing, False = create new.
        change_nature: One of ``new_interface``, ``schema``, ``behavior``, ``config``.
        description: What changes in this component.
        proposed_dal: The assigned DO-178C DAL level for this component (e.g., DAL_A, DAL_B, DAL_C, DAL_D, DAL_E). This MUST be explicitly provided.
        dependencies: Other components that must be changed first.
        confidence: LLM's confidence in this proposal (0-100).
    """

    component: str
    exists: bool
    change_nature: str
    description: str
    proposed_dal: DALLevel = Field(description="The DO-178C DAL rating required: DAL_A, DAL_B, DAL_C, DAL_D, or DAL_E")
    dependencies: list[str] = Field(default_factory=list)
    confidence: int = 0


class IntegrationSeam(BaseModel):
    """A connection between two components affected by a feature.

    Attributes:
        between: Ordered pair of component names.
        contract: What is exchanged (event name, API endpoint, shared type).
        format: Communication mechanism (``event``, ``API call``, ``shared type``).
        confidence: LLM's confidence in this seam (0-100).
    """

    between: tuple[str, str]
    contract: str
    format: str
    confidence: int = 0


class DecompositionPlan(BaseModel):
    """Full decomposition output for a feature.

    ``coverage_score`` and ``alignment_notes`` exist so a future
    auto-gate can replace the HITL review with quantified criteria.

    Attributes:
        feature_spec: Path to the source Feature Spec.
        components: Affected components with change details.
        integration_seams: Cross-component connections.
        build_sequence: Ordered list of component names for implementation.
        coverage_score: Fraction of Blast Radius entries covered (0.0-1.0).
        alignment_notes: Topology matches/mismatches (signals, not errors).
        timestamp: ISO-8601 timestamp of plan creation.
    """

    feature_spec: str
    components: list[ComponentChange]
    integration_seams: list[IntegrationSeam]
    build_sequence: list[str]
    coverage_score: float
    alignment_notes: list[str] = Field(default_factory=list)
    timestamp: str
