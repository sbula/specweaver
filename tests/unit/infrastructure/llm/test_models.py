from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig


def test_prompt_safe_config_instantiation() -> None:
    """Test instantiation of PromptSafeConfig model."""
    config = PromptSafeConfig(
        llm_model="gemini-1.5-pro",
        llm_provider="gemini",
        validation_rules={"S01": True},
    )
    assert config.llm_model == "gemini-1.5-pro"
    assert config.llm_provider == "gemini"
    assert config.validation_rules == {"S01": True}


def test_project_metadata_instantiation() -> None:
    """Test instantiation of ProjectMetadata model."""
    config = PromptSafeConfig(
        llm_model="gemini-1.5-pro",
        llm_provider="gemini",
        validation_rules={"S01": True},
    )
    meta = ProjectMetadata(
        project_name="specweaver_test",
        archetype="library",
        language_target="Python 3.12.0 on Windows-10",
        date_iso="2026-03-29T12:00:00Z",
        safe_config=config,
    )
    assert meta.project_name == "specweaver_test"
    assert meta.archetype == "library"
    assert meta.language_target == "Python 3.12.0 on Windows-10"
    assert meta.date_iso == "2026-03-29T12:00:00Z"
    assert meta.safe_config == config
