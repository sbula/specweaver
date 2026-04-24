import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.commons.enums.dal import DALLevel

@pytest.fixture
def mock_project_path(tmp_path: Path) -> Path:
    proj = tmp_path / "test_dal_project"
    proj.mkdir()
    (proj / "context.yaml").write_text("operational:\n  dal_level: DAL_D")
    return proj


def test_pipeline_runner_injects_dal_level(mock_project_path: Path):
    """PipelineRunner should resolve and inject DALLevel into RunContext."""
    from specweaver.core.flow.handlers.base import RunContext
    context = RunContext(project_path=mock_project_path, spec_path=mock_project_path / "spec.yaml")
    pipeline = MagicMock()
    runner = PipelineRunner(pipeline=pipeline, context=context)
    # Runner calls DALResolver internally and defaults to the project root context
    assert context.dal_level is not None
    assert context.dal_level.value == "DAL_D"
    assert not context.dal_level.is_strict

def test_pipeline_runner_injects_strict_dal_level(tmp_path: Path):
    proj = tmp_path / "strict_dal_project"
    proj.mkdir()
    (proj / "context.yaml").write_text("operational:\n  dal_level: DAL_A")
    from specweaver.core.flow.handlers.base import RunContext
    context = RunContext(project_path=proj, spec_path=proj / "spec.yaml")
    pipeline = MagicMock()
    runner = PipelineRunner(pipeline=pipeline, context=context)
    assert context.dal_level is not None
    assert context.dal_level.value == "DAL_A"
    assert context.dal_level.is_strict

def test_pipeline_runner_passes_dal_level_to_context(mock_project_path: Path):
    """Ensure the DALLevel makes it into the RunContext created for step handlers."""
    from specweaver.core.flow.handlers.base import RunContext
    context = RunContext(project_path=mock_project_path, spec_path=mock_project_path / "spec.yaml")
    pipeline = MagicMock()
    pipeline.steps = []
    runner = PipelineRunner(pipeline=pipeline, context=context)
    
    assert context.dal_level is not None
    assert context.dal_level.value == "DAL_D"
