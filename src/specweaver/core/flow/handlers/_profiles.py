"""Named prompt render profile constants.

These constants encode workflow orchestration policy — they declare which
prompt slots are active for each handler archetype and in what order
they are rendered. They live in the orchestrator layer, NOT in
infrastructure, following the Mechanism/Policy DDD split (AD-1).

Usage by handlers::

    from specweaver.core.flow.handlers._profiles import FULL, MINIMAL

    base_prompt = await _build_base_prompt(context, instructions, profile=FULL)
"""

from specweaver.infrastructure.llm._prompt_profiles import PromptSlot, RenderProfile

# ---------------------------------------------------------------------------
# Standard rendering order (matches current hardcoded sequence in
# _prompt_render.py:73-116 for backward compatibility)
# ---------------------------------------------------------------------------

_STANDARD_ORDER: tuple[PromptSlot, ...] = (
    PromptSlot.INSTRUCTIONS,
    PromptSlot.DICTATOR_OVERRIDES,
    PromptSlot.METADATA,
    PromptSlot.CONSTITUTION,
    PromptSlot.STANDARDS,
    PromptSlot.PLAN,
    PromptSlot.TOPOLOGY,
    PromptSlot.FILE,
    PromptSlot.MENTIONED,
    PromptSlot.CONTEXT,
    PromptSlot.AGENT_MEMORY,
    PromptSlot.REMINDER,
)

_ALL_SLOTS = frozenset(PromptSlot)

# ---------------------------------------------------------------------------
# Named Profiles (FR-3)
# ---------------------------------------------------------------------------

FULL = RenderProfile(
    name="FULL",
    active_slots=_ALL_SLOTS,
    order=_STANDARD_ORDER,
)
"""Full profile — all slots active. Used by generators and reviewers."""

MINIMAL = RenderProfile(
    name="MINIMAL",
    active_slots=frozenset({
        PromptSlot.INSTRUCTIONS,
        PromptSlot.METADATA,
        PromptSlot.TOPOLOGY,
    }),
    order=(
        PromptSlot.INSTRUCTIONS,
        PromptSlot.METADATA,
        PromptSlot.TOPOLOGY,
    ),
)
"""Minimal profile — instructions + metadata + topology only.
Used by the Decomposer and Planner."""

INTERACTIVE = RenderProfile(
    name="INTERACTIVE",
    active_slots=_ALL_SLOTS - frozenset({
        PromptSlot.CONSTITUTION,
        PromptSlot.STANDARDS,
    }),
    order=tuple(
        s for s in _STANDARD_ORDER
        if s not in {PromptSlot.CONSTITUTION, PromptSlot.STANDARDS}
    ),
)
"""Interactive profile — all slots except constitution and standards.
Used by the Drafter for interactive spec authoring."""

ARBITER = RenderProfile(
    name="ARBITER",
    active_slots=frozenset({
        PromptSlot.INSTRUCTIONS,
        PromptSlot.CONTEXT,
    }),
    order=(
        PromptSlot.INSTRUCTIONS,
        PromptSlot.CONTEXT,
    ),
)
"""Arbiter profile — instructions + context only.
Used by the ArbitrateVerdictHandler for minimal, focused arbitration."""
