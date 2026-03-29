# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for Phase 3 API schemas (pipeline execution)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from specweaver.api.v1.schemas import (
    GateDecisionRequest,
    PipelineRunRequest,
    PipelineRunResponse,
)


class TestPipelineRunRequest:
    """Tests for PipelineRunRequest schema (#51, #52)."""

    def test_requires_project_and_spec(self) -> None:
        """PipelineRunRequest requires project and spec fields."""
        with pytest.raises(ValidationError):
            PipelineRunRequest()  # type: ignore[call-arg]

    def test_valid_request(self) -> None:
        """PipelineRunRequest accepts valid project + spec."""
        req = PipelineRunRequest(project="myproj", spec="spec.md")
        assert req.project == "myproj"
        assert req.spec == "spec.md"

    def test_selector_defaults_to_direct(self) -> None:
        """PipelineRunRequest.selector defaults to 'direct'."""
        req = PipelineRunRequest(project="myproj", spec="spec.md")
        assert req.selector == "direct"

    def test_selector_override(self) -> None:
        """PipelineRunRequest.selector can be overridden."""
        req = PipelineRunRequest(project="myproj", spec="spec.md", selector="topological")
        assert req.selector == "topological"


class TestGateDecisionRequest:
    """Tests for GateDecisionRequest schema (#53)."""

    def test_requires_action(self) -> None:
        """GateDecisionRequest requires an action field."""
        with pytest.raises(ValidationError):
            GateDecisionRequest()  # type: ignore[call-arg]

    def test_valid_approve(self) -> None:
        """GateDecisionRequest accepts 'approve'."""
        req = GateDecisionRequest(action="approve")
        assert req.action == "approve"

    def test_valid_reject(self) -> None:
        """GateDecisionRequest accepts 'reject'."""
        req = GateDecisionRequest(action="reject")
        assert req.action == "reject"


class TestPipelineRunResponse:
    """Tests for PipelineRunResponse schema."""

    def test_response_fields(self) -> None:
        """PipelineRunResponse has run_id and detail."""
        resp = PipelineRunResponse(run_id="abc-123", detail="Started.")
        assert resp.run_id == "abc-123"
        assert resp.detail == "Started."
