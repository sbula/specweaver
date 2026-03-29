from specweaver.llm.models import ProjectMetadata, PromptSafeConfig
from specweaver.llm.prompt_builder import PromptBuilder


def test_prompt_builder_adds_project_metadata() -> None:
    """Test that ProjectMetadata is successfully formatted and attached."""
    config = PromptSafeConfig(
        llm_model="gemini-1.5-pro",
        llm_provider="gemini",
        validation_rules={"S01": True},
    )
    meta = ProjectMetadata(
        project_name="my_proj",
        archetype="api",
        language_target="Python 3.11",
        date_iso="2026-03-29",
        safe_config=config,
    )

    prompt = PromptBuilder().add_project_metadata(meta).build()

    assert "<project_metadata>" in prompt
    assert "my_proj" in prompt
    assert "gemini-1.5-pro" in prompt
    assert "S01" in prompt


def test_prompt_builder_skips_metadata_if_none() -> None:
    """Test that None metadata is safely ignored."""
    prompt = PromptBuilder().add_project_metadata(None).build()
    assert "<project_metadata>" not in prompt
