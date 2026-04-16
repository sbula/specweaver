# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for the scenario pipeline execution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from ruamel.yaml import YAML

from specweaver.core.flow._base import RunContext
from specweaver.core.flow.models import PipelineDefinition
from specweaver.core.flow.runner import PipelineRunner


@pytest.fixture()
def scenario_pipeline_path() -> Path:
    """Path to the real scenario validation pipeline."""
    p = Path("src/specweaver/workflows/pipelines/scenario_validation.yaml")
    assert p.exists(), "Pipeline YAML missing"
    return p


@pytest.fixture()
def project_workspace(tmp_path: Path) -> Path:
    """Setup a sample project with a spec."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    spec_path = spec_dir / "auth_spec.md"
    spec_path.write_text(
        "# Auth\n\n"
        "## Functional Requirements\n\n| FR-1 | Login |\n\n"
        "## Contract\n\ndef login(u, p): ...\n\n",
        encoding="utf-8",
    )

    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    contract_path = contracts_dir / "auth_contract.py"
    contract_path.write_text("class AuthProtocol: ...", encoding="utf-8")

    return tmp_path


@pytest.mark.asyncio()
async def test_scenario_pipeline_end_to_end_integration(
    project_workspace: Path, scenario_pipeline_path: Path
) -> None:
    """Full integration test combining GenerateScenarioHandler and ConvertScenarioHandler.

    Verifies that the YAML artifact is successfully transitioned between steps
    on the physical filesystem.
    """
    yaml = YAML(typ="safe")
    pipeline_data = yaml.load(scenario_pipeline_path.read_text())
    # Remove the `generate_contract` step for this test, we already stubbed the contract
    pipeline_data["steps"] = [s for s in pipeline_data["steps"] if s["name"] != "generate_contract"]
    definition = PipelineDefinition.model_validate(pipeline_data)

    mock_llm = AsyncMock()
    valid_response = {
        "spec_path": "specs/auth_spec.md",
        "contract_path": "contracts/auth_contract.py",
        "scenarios": [
            {
                "name": "integration_scenario",
                "description": "Integration test",
                "function_under_test": "login",
                "req_id": "FR-1",
                "category": "happy",
            },
        ],
    }
    mock_llm.generate.return_value = json.dumps(valid_response)

    ctx = MagicMock(spec=RunContext)
    ctx.spec_path = project_workspace / "specs" / "auth_spec.md"
    ctx.project_path = project_workspace
    ctx.llm = mock_llm
    ctx.api_contract_paths = [str(project_workspace / "contracts" / "auth_contract.py")]
    ctx.constitution = None
    ctx.project_metadata = None
    ctx.config = None
    ctx.llm_routing_enabled = False
    ctx.llm_router = None
    ctx.generation_config = None
    ctx.feedback = {}

    runner = PipelineRunner(definition, ctx)
    result = await runner.run()

    from specweaver.core.flow.state import RunStatus

    assert result.status == RunStatus.COMPLETED

    # Validate Generation Output
    scenario_dir = project_workspace / "scenarios" / "definitions"
    yaml_file = scenario_dir / "auth_scenarios.yaml"
    assert yaml_file.exists()

    # Validate Conversion Output
    test_dir = project_workspace / "scenarios" / "generated"
    py_file = test_dir / "test_auth_scenarios.py"
    assert py_file.exists()

    content = py_file.read_text()
    assert "def test_login_happy():" in content
    assert "@trace(FR-1)" in content
