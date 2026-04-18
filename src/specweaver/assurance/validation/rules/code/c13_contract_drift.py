# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C13: Contract Drift Analysis — checks for missing protocol endpoints in code."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


class C13ContractDriftRule(Rule):
    """Enforces protocol contract boundaries against tree-sitter AST mapped paths.

    Expects `protocol_schema` and `ast_payload` in the execution context.
    If either is missing, it skips execution safely.
    """

    @property
    def rule_id(self) -> str:
        return "C13"

    @property
    def name(self) -> str:
        return "Contract Drift Analysis"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        protocol_endpoints = self.context.get("protocol_schema")
        ast_payload = self.context.get("ast_payload")

        if protocol_endpoints is None or ast_payload is None:
            return self._skip("Missing 'protocol_schema' or 'ast_payload' in context")

        findings: list[Finding] = []

        ast_marker_string = str(ast_payload)

        # Iterate through protocol endpoints to ensure they exist in the AST logic
        if not isinstance(protocol_endpoints, list):
            protocol_endpoints = [protocol_endpoints]

        for endpoint in protocol_endpoints:
            if not isinstance(endpoint, dict) and not hasattr(endpoint, "path"):
                continue

            # ProtocolEndpoint instances or simple dictionary exports
            path = (
                endpoint.get("path")
                if isinstance(endpoint, dict)
                else getattr(endpoint, "path", None)
            )
            method = (
                endpoint.get("method", "ANY").upper()
                if isinstance(endpoint, dict)
                else getattr(endpoint, "method", "ANY").upper()
            )

            if not path:
                continue

            # Native drift check: Does the exact path show up in the AST routing bindings?
            matched = path in ast_marker_string

            if not matched:
                findings.append(
                    Finding(
                        message=f"Contract Drift: Endpoint '{method} {path}' declared in protocol but missing from code AST routing.",
                        severity=Severity.ERROR,
                        suggestion=f"Implement the missing routing endpoint '{path}' in the source file.",
                    )
                )

        if findings:
            return self._fail(
                f"Contract Drift Detected: {len(findings)} unanchored endpoints.", findings
            )

        return self._pass("All protocol endpoints dynamically mapped to AST successfully.")
