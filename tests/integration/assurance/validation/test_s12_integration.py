# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import json
from pathlib import Path

from specweaver.assurance.validation.executor import execute_validation_pipeline
from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml


def test_s12_integration_via_pipeline(tmp_path: Path) -> None:
    """Verify S12 seamlessly acts on injected AST payloads inside the validation executor pipeline."""

    # 1. Load the real default Spec pipeline
    pipeline = load_pipeline_yaml("validation_spec_default")

    # Ensure S12 is injected with parameters
    for step in pipeline.steps:
        if step.rule == "S12":
            step.params["required_headers"] = {
                "h1": ["Mock Title"],
                "h2": ["1. Purpose", "2. Boundaries"],
            }
            # Injecting mock payload matching flow bounds
            step.params["ast_payload"] = {
                "structure": json.dumps(
                    {
                        "h1": ["Mock Title"],
                        "h2": ["Some other section", "1. Purpose"],  # Missing '2. Boundaries'
                    }
                )
            }
            break

    # 2. Execute
    spec_txt = "# Mock Title\n\n## Some other section\n\n## 1. Purpose"
    results = execute_validation_pipeline(pipeline, spec_txt, Path("spec.md"))

    # 3. Assess
    s12_result = next((r for r in results if r.rule_id == "S12"), None)

    assert s12_result is not None, "S12 rule should be evaluated."
    assert s12_result.status == Status.FAIL
    assert len(s12_result.findings) == 1
    assert "Missing required <h2> header: '2. Boundaries'" in s12_result.findings[0].message
