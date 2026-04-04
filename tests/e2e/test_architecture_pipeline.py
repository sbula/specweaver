# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests for Architecture Checks in Validation Pipelines and Agents."""

import pytest
from pathlib import Path

from specweaver.validation.pipeline_loader import load_pipeline_yaml
from specweaver.validation.executor import execute_validation_pipeline
from specweaver.validation.models import Status
from specweaver.config.settings import ValidationSettings

@pytest.fixture
def architecture_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with an architecture violation."""
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True)

    src = tmp_path / "src" / "my_project"
    src.mkdir(parents=True)
    
    (src / "__init__.py").touch()
    
    core = src / "core"
    core.mkdir()
    (core / "__init__.py").touch()
    
    ui = src / "ui"
    ui.mkdir()
    (ui / "__init__.py").touch()
    
    # Violation: core imports ui
    bad_core = core / "bad_impl.py"
    bad_core.write_text("from my_project.ui import something\ndef fn(): pass\n")
    
    tach_toml = tmp_path / "tach.toml"
    tach_toml.write_text("""exact = true
source_roots = ["src"]

[[modules]]
path = "<root>"
depends_on = ["my_project.core", "my_project.ui"]

[[modules]]
path = "my_project.core"
depends_on = [] 

[[modules]]
path = "my_project.ui"
depends_on = ["my_project.core"]
""")
    return tmp_path

class TestArchitectureE2E:
    @pytest.mark.asyncio
    async def test_validation_pipeline_fails_on_architecture(self, architecture_workspace: Path) -> None:
        """Story 7: Pipeline natively aborts on C05 failure."""
        target_file = architecture_workspace / "src" / "my_project" / "core" / "bad_impl.py"
        code = target_file.read_text()
        
        # Load the code validation pipeline
        pipeline = load_pipeline_yaml("validation_code_default")
        settings = ValidationSettings()
        
        # We need to execute the pipeline with the correct file path to trigger Tach
        # In a real environment the graph topology / node context provides this
        # but execute_validation_pipeline takes `spec_path`.
        
        results = execute_validation_pipeline(pipeline, code, spec_path=target_file)
        
        c05 = next(r for r in results if r.rule_id == "C05")
        assert c05.status == Status.FAIL
        assert "architectural violation" in c05.message.lower()

    @pytest.mark.asyncio
    async def test_agent_tool_can_run_architecture(self, architecture_workspace: Path) -> None:
        """Story 8: E2E tool capability for agent role 'implementer'."""
        from specweaver.loom.tools.qa_runner.interfaces import create_qa_runner_interface
        
        # Instantiate the Implementer role tool
        tool_interface = create_qa_runner_interface(role="implementer", cwd=architecture_workspace)
        
        # Run the architecture tool manually as an agent would
        result = tool_interface.run_architecture(target=".")
        
        # It should report an error status because the target is invalid architecture
        assert result.status == "error"
        assert result.data
        assert result.data.get("violation_count", 0) == 1
        assert "UndeclaredDependency" in str(result.data.get("violations"))
