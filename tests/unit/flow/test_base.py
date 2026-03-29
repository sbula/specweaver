from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.flow._base import RunContext
from specweaver.llm.models import ProjectMetadata


def test_run_context_builds_project_metadata(tmp_path: Path) -> None:
    """Test that RunContext correctly builds the metadata DTO."""
    (tmp_path / "context.yaml").write_text("archetype: web-service\n", encoding="utf-8")

    config = MagicMock()
    config.validation.overrides = {"S01": True}
    llm = MagicMock()
    llm.provider_name = "mock_provider"
    llm.model = "mock-model"
    db = MagicMock()

    context = RunContext(
        llm=llm,
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
        db=db,
        config=config,
    )

    assert isinstance(context.project_metadata, ProjectMetadata)
    assert context.project_metadata.project_name == tmp_path.name
    assert context.project_metadata.safe_config.llm_model == "mock-model"
    assert context.project_metadata.safe_config.llm_provider == "mock_provider"
    assert context.project_metadata.safe_config.validation_rules == {"S01": True}
    assert context.project_metadata.archetype == "web-service"


def test_run_context_graceful_degradation(tmp_path: Path) -> None:
    """Test fallback when platform module raises an exception."""
    config = MagicMock()
    config.validation = MagicMock()
    config.validation.overrides = {}
    llm = MagicMock()
    llm.provider_name = "test"
    llm.model = "test"
    db = MagicMock()

    with patch("platform.platform", side_effect=Exception("err")):
        context = RunContext(
            llm=llm,
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            db=db,
            config=config,
        )

    assert context.project_metadata.language_target == "Unknown Environment"
