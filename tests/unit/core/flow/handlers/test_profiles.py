from dataclasses import FrozenInstanceError

import pytest

from specweaver.core.flow.handlers._profiles import (
    _STANDARD_ORDER,
    ARBITER,
    FULL,
    INTERACTIVE,
    MINIMAL,
)
from specweaver.infrastructure.llm._prompt_profiles import PromptSlot, RenderProfile


class TestPolicyProfiles:
    def test_full_profile_all_slots_active(self) -> None:
        """P1: FULL includes every slot."""
        assert FULL.active_slots == frozenset(PromptSlot)

    def test_full_profile_order_is_standard(self) -> None:
        """P2: FULL ordering matches the standard sequence."""
        assert FULL.order == _STANDARD_ORDER

    def test_minimal_profile_exact_slots(self) -> None:
        """P3: MINIMAL has exactly 3 slots."""
        assert MINIMAL.active_slots == frozenset({
            PromptSlot.INSTRUCTIONS,
            PromptSlot.METADATA,
            PromptSlot.TOPOLOGY,
        })

    def test_minimal_profile_order(self) -> None:
        """P4: MINIMAL order matches its active_slots."""
        assert set(MINIMAL.order) == MINIMAL.active_slots

    def test_interactive_excludes_constitution_standards(self) -> None:
        """P5: INTERACTIVE has all slots EXCEPT CONSTITUTION and STANDARDS."""
        assert PromptSlot.CONSTITUTION not in INTERACTIVE.active_slots
        assert PromptSlot.STANDARDS not in INTERACTIVE.active_slots

    def test_interactive_includes_agent_memory(self) -> None:
        """P6: INTERACTIVE includes AGENT_MEMORY."""
        assert PromptSlot.AGENT_MEMORY in INTERACTIVE.active_slots

    def test_interactive_slot_count(self) -> None:
        """P7: INTERACTIVE has exactly 10 slots."""
        assert len(INTERACTIVE.active_slots) == 10

    def test_arbiter_exact_slots(self) -> None:
        """P8: ARBITER has exactly 2 slots."""
        assert ARBITER.active_slots == frozenset({
            PromptSlot.INSTRUCTIONS,
            PromptSlot.CONTEXT,
        })

    def test_all_profiles_pass_validation(self) -> None:
        """P9: All 4 profiles satisfy the order == active_slots invariant."""
        profiles = [FULL, MINIMAL, INTERACTIVE, ARBITER]
        for p in profiles:
            assert set(p.order) == p.active_slots
            # Force post_init validation again just to be absolutely certain
            RenderProfile(name=p.name, active_slots=p.active_slots, order=p.order)

    def test_profiles_are_distinct(self) -> None:
        """P10: No two profiles are equal."""
        profiles = [FULL, MINIMAL, INTERACTIVE, ARBITER]
        for i, p1 in enumerate(profiles):
            for j, p2 in enumerate(profiles):
                if i != j:
                    assert p1 != p2

    def test_profiles_are_frozen(self) -> None:
        """P11: All profiles reject attribute mutation."""
        for p in [FULL, MINIMAL, INTERACTIVE, ARBITER]:
            with pytest.raises(FrozenInstanceError):
                p.name = "hacked" # type: ignore

    def test_standard_order_matches_enum_definition(self) -> None:
        """P12: _STANDARD_ORDER matches tuple(PromptSlot). Ensures backward compat without boundary violation."""
        assert tuple(PromptSlot) == _STANDARD_ORDER

    def test_full_profile_name(self) -> None:
        """P13: Profile names are correct for logging."""
        assert FULL.name == "FULL"
        assert MINIMAL.name == "MINIMAL"
        assert INTERACTIVE.name == "INTERACTIVE"
        assert ARBITER.name == "ARBITER"
