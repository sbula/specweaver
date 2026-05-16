from dataclasses import FrozenInstanceError

import pytest

from specweaver.infrastructure.llm._prompt_profiles import (
    _DEFAULT_PROFILE,
    PromptSlot,
    RenderProfile,
)


class TestPromptSlot:
    def test_prompt_slot_is_str_enum(self) -> None:
        """T1: Ensure PromptSlot members are strings and directly comparable."""
        assert isinstance(PromptSlot.INSTRUCTIONS, str)
        assert PromptSlot.INSTRUCTIONS.value == "instructions"

    def test_prompt_slot_all_11_base_kinds_present(self) -> None:
        """T2: Ensure all 11 existing _ContentBlock.kind values are mapped."""
        assert PromptSlot.INSTRUCTIONS.value == "instructions"
        assert PromptSlot.DICTATOR_OVERRIDES.value == "dictator-overrides"
        assert PromptSlot.METADATA.value == "project_metadata"
        assert PromptSlot.CONSTITUTION.value == "constitution"
        assert PromptSlot.STANDARDS.value == "standards"
        assert PromptSlot.PLAN.value == "plan"
        assert PromptSlot.TOPOLOGY.value == "topology"
        assert PromptSlot.FILE.value == "file"
        assert PromptSlot.MENTIONED.value == "mentioned"
        assert PromptSlot.CONTEXT.value == "context"
        assert PromptSlot.REMINDER.value == "reminder"

    def test_prompt_slot_agent_memory_present(self) -> None:
        """T3: Ensure forward-looking slot exists."""
        assert PromptSlot.AGENT_MEMORY.value == "agent_memory"

    def test_prompt_slot_total_count(self) -> None:
        """T4: Ensure exactly 12 members are defined."""
        assert len(PromptSlot) == 12

    def test_prompt_slot_values_unique(self) -> None:
        """T14: No two enum members share the same string value."""
        values = [s.value for s in PromptSlot]
        assert len(set(values)) == len(PromptSlot)


class TestRenderProfile:
    def test_render_profile_creation_valid(self) -> None:
        """T5: Happy path: valid profile with order exactly matching active_slots."""
        profile = RenderProfile(
            name="test_profile",
            active_slots=frozenset({PromptSlot.INSTRUCTIONS, PromptSlot.CONTEXT}),
            order=(PromptSlot.INSTRUCTIONS, PromptSlot.CONTEXT),
        )
        assert profile.name == "test_profile"
        assert profile.active_slots == frozenset({PromptSlot.INSTRUCTIONS, PromptSlot.CONTEXT})
        assert profile.order == (PromptSlot.INSTRUCTIONS, PromptSlot.CONTEXT)

    def test_render_profile_order_mismatch_violation(self) -> None:
        """T6: order contains slot NOT in active_slots OR misses active slots."""
        # Missing active slot
        with pytest.raises(ValueError, match="active but not ordered"):
            RenderProfile(
                name="test_missing",
                active_slots=frozenset({PromptSlot.INSTRUCTIONS, PromptSlot.CONTEXT}),
                order=(PromptSlot.INSTRUCTIONS,),
            )

        # Extra ordered slot
        with pytest.raises(ValueError, match="ordered but not active"):
            RenderProfile(
                name="test_extra",
                active_slots=frozenset({PromptSlot.INSTRUCTIONS}),
                order=(PromptSlot.INSTRUCTIONS, PromptSlot.CONTEXT),
            )

    def test_render_profile_duplicate_order_violation(self) -> None:
        """T7: order contains duplicate slots."""
        with pytest.raises(ValueError, match="order contains duplicate slots"):
            RenderProfile(
                name="test_dup",
                active_slots=frozenset({PromptSlot.INSTRUCTIONS}),
                order=(PromptSlot.INSTRUCTIONS, PromptSlot.INSTRUCTIONS),
            )

    def test_render_profile_frozen(self) -> None:
        """T8: Profile attributes are immutable."""
        profile = RenderProfile(
            name="test_frozen",
            active_slots=frozenset({PromptSlot.INSTRUCTIONS}),
            order=(PromptSlot.INSTRUCTIONS,),
        )
        with pytest.raises(FrozenInstanceError):
            profile.name = "mutated"  # type: ignore
        with pytest.raises(FrozenInstanceError):
            profile.active_slots = frozenset()  # type: ignore

    def test_render_profile_equality_by_value(self) -> None:
        """T9: Two profiles with same fields are equal."""
        profile_a = RenderProfile(
            name="test_eq",
            active_slots=frozenset({PromptSlot.INSTRUCTIONS}),
            order=(PromptSlot.INSTRUCTIONS,),
        )
        profile_b = RenderProfile(
            name="test_eq",
            active_slots=frozenset({PromptSlot.INSTRUCTIONS}),
            order=(PromptSlot.INSTRUCTIONS,),
        )
        assert profile_a == profile_b
        assert profile_a is not profile_b

    def test_render_profile_empty_active_slots(self) -> None:
        """T10: Empty active_slots + empty order is valid."""
        profile = RenderProfile(name="test_empty", active_slots=frozenset(), order=())
        assert len(profile.active_slots) == 0
        assert len(profile.order) == 0

    def test_render_profile_name_in_repr(self) -> None:
        """T11: Name appears in repr for debugging."""
        profile = RenderProfile(name="test_repr_name", active_slots=frozenset(), order=())
        assert "test_repr_name" in repr(profile)

    def test_render_profile_single_slot(self) -> None:
        """T15: Profile with exactly 1 slot is valid."""
        profile = RenderProfile(
            name="single",
            active_slots=frozenset({PromptSlot.INSTRUCTIONS}),
            order=(PromptSlot.INSTRUCTIONS,),
        )
        assert profile.name == "single"
        assert len(profile.active_slots) == 1


class TestDefaultProfile:
    def test_default_profile_all_slots_active(self) -> None:
        """T12: _DEFAULT_PROFILE has all 12 slots active."""
        assert _DEFAULT_PROFILE.active_slots == frozenset(PromptSlot)

    def test_default_profile_order_matches_standard(self) -> None:
        """T13: _DEFAULT_PROFILE.order matches the enum definition order."""
        assert _DEFAULT_PROFILE.order == tuple(PromptSlot)
