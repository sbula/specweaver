"""Prompt slot registry and render profile mechanism types.

Domain-agnostic data structures used by the prompt rendering pipeline.
Profile constants encoding workflow orchestration policy are defined
separately in ``core/flow/handlers/_profiles.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PromptSlot(StrEnum):
    """Registry of all valid prompt block slots.

    Each member's string value IS the XML tag name used in rendering.
    This eliminates any implicit ``kind ↔ slot`` mapping — comparison
    is a direct ``block.kind == slot.value`` string match.

    Slots with custom rendering (FILE, MENTIONED, CONTEXT) still need
    dedicated render functions in ``_prompt_render.py`` but participate
    in the profile filtering and ordering system.
    """

    INSTRUCTIONS = "instructions"
    DICTATOR_OVERRIDES = "dictator-overrides"
    METADATA = "project_metadata"
    CONSTITUTION = "constitution"
    STANDARDS = "standards"
    PLAN = "plan"
    TOPOLOGY = "topology"
    FILE = "file"
    MENTIONED = "mentioned"
    CONTEXT = "context"
    AGENT_MEMORY = "agent_memory"
    REMINDER = "reminder"


@dataclass(frozen=True)
class RenderProfile:
    """Immutable prompt rendering profile.

    Defines which prompt slots are active and in what order they are
    rendered. This is a domain-agnostic mechanism type — it knows about
    slots and ordering, not about workflow semantics.

    The ``order`` tuple is the **sole source of truth** for rendering
    sequence (AD-2). Every active slot MUST appear in ``order`` — there
    is no implicit tail rendering.

    Invariant: ``set(order) == active_slots`` (strict equality)

    Args:
        name: Human-readable profile name (for logging/debugging).
        active_slots: The set of slots that are enabled in this profile.
        order: The rendering sequence. Must exactly match active_slots.
    """

    name: str
    active_slots: frozenset[PromptSlot]
    order: tuple[PromptSlot, ...]

    def __post_init__(self) -> None:
        """Validate that order exactly matches active_slots."""
        order_set = set(self.order)
        if order_set != self.active_slots:
            missing = self.active_slots - order_set
            extra = order_set - self.active_slots
            parts = []
            if missing:
                parts.append(f"active but not ordered: {missing}")
            if extra:
                parts.append(f"ordered but not active: {extra}")
            raise ValueError(
                f"RenderProfile '{self.name}': order must exactly match "
                f"active_slots. {'; '.join(parts)}"
            )
        if len(self.order) != len(order_set):
            raise ValueError(
                f"RenderProfile '{self.name}': order contains duplicate slots"
            )


# ---------------------------------------------------------------------------
# Anonymous backward-compatibility default (FR-9)
# Used internally by PromptBuilder when no profile is explicitly provided.
# This MUST NOT be imported from core/flow/ — it is infrastructure-internal.
# ---------------------------------------------------------------------------

_DEFAULT_PROFILE = RenderProfile(
    name="_default",
    active_slots=frozenset(PromptSlot),
    order=tuple(PromptSlot),
)
