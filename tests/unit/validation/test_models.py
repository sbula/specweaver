# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for validation models."""

from specweaver.validation.models import DriftFinding, DriftReport


class TestDriftModels:
    def test_drift_finding_construction(self) -> None:
        f = DriftFinding(
            severity="error",
            node_type="function",
            description="Missing expected method detect_drift",
            expected_signature="def detect_drift(ast, plan)",
            actual_signature=None,
        )
        assert f.severity == "error"
        assert f.node_type == "function"
        assert f.actual_signature is None

    def test_drift_report_construction(self) -> None:
        r = DriftReport(
            is_drifted=True,
            findings=[
                DriftFinding(
                    severity="error",
                    node_type="class",
                    description="Missing class",
                    expected_signature="class Foo:",
                )
            ],
        )
        assert r.is_drifted is True
        assert len(r.findings) == 1
