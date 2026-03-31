from specweaver.llm.prompt_builder import PromptBuilder


class TestAddArtifactTagging:
    """Test artifact tagging instruction injection."""

    def test_add_artifact_tagging_supported_language(self) -> None:
        """Supported language adds priority 0 instruction that survives truncation."""
        from specweaver.llm.models import TokenBudget

        # Budget of 5 tokens forces truncation; priority 0 must survive.
        budget = TokenBudget(limit=5)
        pb = PromptBuilder(budget=budget)
        pb.add_artifact_tagging("1234", "python")
        pb.add_context("A" * 1000, "filler", priority=1)

        result = pb.build()
        assert "<instructions>" in result
        assert "# sw-artifact: 1234" in result
        assert "physically at the very top" in result

        # Verify it was natively added with priority 0
        tag_block = next(b for b in pb._blocks if "sw-artifact" in b.text)
        assert tag_block.priority == 0

    def test_add_artifact_tagging_unsupported_language(self) -> None:
        """Unsupported language silently ignores the instruction."""
        pb = PromptBuilder()
        pb.add_artifact_tagging("1234", "json")
        result = pb.build()
        assert "<instructions>" not in result
        assert "sw-artifact" not in result

    def test_add_artifact_tagging_empty_id(self) -> None:
        """Empty ID safely does nothing."""
        pb = PromptBuilder()
        pb.add_artifact_tagging("", "python")
        result = pb.build()
        assert "<instructions>" not in result

    def test_add_artifact_tagging_chaining(self) -> None:
        """Method returns self for chaining."""
        pb = PromptBuilder()
        ret = pb.add_artifact_tagging("123", "python")
        assert ret is pb
