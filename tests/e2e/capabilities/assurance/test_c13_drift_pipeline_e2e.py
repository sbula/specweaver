# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import pytest

from specweaver.assurance.validation.executor import execute_validation_pipeline
from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
from specweaver.core.loom.commons.protocol.models import ProtocolEndpoint


def test_c13_contract_drift_engine_pipeline_e2e() -> None:
    """E2E Test: Boot up the full validation pipeline, run C13 drift rule natively."""

    # Load the global code validation YAML natively
    pipeline = load_pipeline_yaml("validation_code_default")

    code_with_drift = """
from fastapi import FastAPI
app = FastAPI()

@app.post("/api/v1/auth")
def auth():
    pass
"""

    # Mock the language evaluator injecting the protocol endpoints directly into context parameter mappings
    # Since we are not triggering a Tool/Atom dynamically from an agent, we mock the global context map for the Runner manually.

    # We will override the Pipeline's context for C13 natively.
    # By default, Executor takes pipeline.rule_configs or we can just mock the context setter before run!

    # Wait, the executor creates Rule instances statically and passes code text. We can patch C13 context logic inside the executor
    # to simulate the upstream Pipeline Orchestrator filling state variables.

    with pytest.MonkeyPatch.context() as m:
        from specweaver.assurance.validation.rules.code.c13_contract_drift import (
            C13ContractDriftRule,
        )

        original_check = C13ContractDriftRule.check

        def mock_check(self, spec_text, spec_path=None):
            self.context = {
                "protocol_schema": [
                    ProtocolEndpoint(
                        path="/api/v1/auth",
                        method="POST",
                        operation_name="auth",
                        expected_response=200,
                    ),
                    ProtocolEndpoint(
                        path="/api/v1/users",
                        method="GET",
                        operation_name="get_users",
                        expected_response=200,
                    ),
                ],
                "ast_payload": {"auth": {"decorators": ["@app.post('/api/v1/auth')"]}},
            }
            return original_check(self, spec_text, spec_path)

        m.setattr(C13ContractDriftRule, "check", mock_check)

        results = execute_validation_pipeline(pipeline, code_with_drift)

        # We expect C13 to execute and Fail
        c13_results = [r for r in results if r.rule_id == "C13"]
        assert len(c13_results) == 1, "C13 must be physically loaded by global pipeline runner"

        drift_result = c13_results[0]
        assert drift_result.status == Status.FAIL
        assert "users" in drift_result.findings[0].message
