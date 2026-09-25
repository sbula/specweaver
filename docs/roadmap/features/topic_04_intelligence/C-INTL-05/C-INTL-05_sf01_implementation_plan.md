# C-INTL-05 SF-01 — Slot Registry & Profile Mechanism

**Status**: COMPLETE (`5b2565b0`, 2026-05-12) · **FRs owned**: FR-1, FR-2, FR-3, FR-9 (anonymous
default profile) · **Depends on**: none · Design: [C-INTL-05_design.md](C-INTL-05_design.md) §Sub-features → SF-01

## Goal

Define the `PromptSlot` str Enum and the `RenderProfile` frozen dataclass — domain-agnostic mechanism
types — in `infrastructure/llm/_prompt_profiles.py`. Define the 4 named profiles (`FULL`, `MINIMAL`,
`INTERACTIVE`, `ARBITER`) as orchestration policy in `core/flow/handlers/_profiles.py`. Expose the
new types in `infrastructure/llm/context.yaml`. Define the FR-9 default that SF-02 wires in.

## Where it plugs in

| Fact | Where |
|---|---|
| `_ContentBlock` uses 11 string `kind` values: `instructions`, `dictator-overrides`, `project_metadata`, `constitution`, `standards`, `plan`, `topology`, `file`, `mentioned`, `context`, `reminder`. Each maps 1:1 to a `PromptSlot` member. | `prompt_builder.py` |
| The hardcoded render order the profiles must reproduce | `_prompt_render.py:73-116` |
| Existing private-module naming the new file follows: `_prompt_constants.py`, `_prompt_render.py` | `infrastructure/llm/` |
| `flow` already `consumes: specweaver/llm`, so `_profiles.py` → `_prompt_profiles` is legal | flow's `context.yaml` |
| `tach.toml` enforces at `src.specweaver.infrastructure.llm` level; both new modules sit inside their own zones; import direction `flow → llm` | `tach.toml` |
| `llm/` is a PEP-420 implicit namespace package — no `__init__.py` update | `infrastructure/llm/` |

## Changes

1. **Mechanism types** · [NEW] `src/specweaver/infrastructure/llm/_prompt_profiles.py` — `PromptSlot`
   (AD-2) and `RenderProfile` (AD-3). Python 3.13 (per `pyproject.toml`), so stdlib `StrEnum` (since
   3.11; `from enum import StrEnum`) — no `str, Enum` inheritance hack.

```python
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
```

   `AGENT_MEMORY` is a forward-looking slot for B-INTL-09 Agent Memory Bank hydration, declared now
   so profiles can reference it without a later enum extension. `_build_base_prompt` memory hydration
   still used `kind="context"` with `label="agent_memory"`; SF-02 migrates it to the dedicated slot.

```python
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
```

   Validation raises `ValueError`, not `assert` — `assert` is disabled under `-O`. The dataclass only
   validates, so a plain `__post_init__` suffices (no `object.__setattr__` normalization).

2. **Expose the types** · [MODIFY] `src/specweaver/infrastructure/llm/context.yaml` (NFR-2 / RT-27).
   Without this, imports from `core/flow/` are an undeclared boundary crossing.

```diff
 exposes:
   - LLMAdapter
   ...
   - wrap_artifact_tag
+  - PromptSlot
+  - RenderProfile
```

3. **Policy constants** · [NEW] `src/specweaver/core/flow/handlers/_profiles.py` — imports `PromptSlot`
   and `RenderProfile` from `infrastructure/llm/_prompt_profiles`.

```python
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
```

   `_STANDARD_ORDER` is the backward-compatible sequence, mirroring `_prompt_render.py:73-116`:
   instructions → dictator-overrides → project_metadata → constitution → standards → plan → topology
   → file → mentioned → context → agent_memory → reminder. SF-02 uses it to replace the hardcoded
   `ordered_tags` list.

4. **FR-9 default** · bottom of `_prompt_profiles.py`. SF-01 only defines it; SF-02 wires the
   deprecation warning and uses it when `PromptBuilder.__init__` gets no `profile`.

```python
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
```

   ALL slots active, enum definition order — so `PromptBuilder()` without a profile renders exactly
   as before (NFR-4). **`tuple(PromptSlot)` must equal `_STANDARD_ORDER`**: the `PromptSlot` member
   order is load-bearing and must not be reordered casually. Both orderings are tested for equality.

| File | Change | FR |
|---|---|---|
| `src/specweaver/infrastructure/llm/_prompt_profiles.py` | NEW — `PromptSlot`, `RenderProfile`, `_DEFAULT_PROFILE` | FR-1, FR-2, FR-9 |
| `src/specweaver/core/flow/handlers/_profiles.py` | NEW — `FULL`, `MINIMAL`, `INTERACTIVE`, `ARBITER` | FR-3 |
| `src/specweaver/infrastructure/llm/context.yaml` | add `PromptSlot`, `RenderProfile` to `exposes` | NFR-2 |
| `tests/unit/infrastructure/llm/test_prompt_profiles.py` | NEW | — |
| `tests/unit/core/flow/handlers/test_profiles.py` | NEW | — |

Commit boundary CB-1: `feat(C-INTL-05/SF-01): add PromptSlot enum and RenderProfile dataclass`

## Tests

Conventions: `pytest`, `@pytest.mark.parametrize`, class-based grouping, `tmp_path`; placement mirrors
source (`tests/unit/infrastructure/llm/`, `tests/unit/core/flow/handlers/`).

`tests/unit/infrastructure/llm/test_prompt_profiles.py` — mechanism types (`PromptSlot`,
`RenderProfile`, `_DEFAULT_PROFILE`):

| # | Test | Story | Asserts |
|---|------|-------|---------|
| T1 | `test_prompt_slot_is_str_enum` | `PromptSlot` members are string values | `isinstance(PromptSlot.INSTRUCTIONS, str)` and `PromptSlot.INSTRUCTIONS == "instructions"` |
| T2 | `test_prompt_slot_all_11_base_kinds_present` | Enum covers all 11 existing `_ContentBlock.kind` values | Each of the 11 kinds has a `PromptSlot` member |
| T3 | `test_prompt_slot_agent_memory_present` | Forward-looking slot exists | `PromptSlot.AGENT_MEMORY == "agent_memory"` |
| T4 | `test_prompt_slot_total_count` | Exactly 12 members | `len(PromptSlot) == 12` |
| T5 | `test_render_profile_creation_valid` | Valid profile, order exactly matching active_slots | No exception raised |
| T6 | `test_render_profile_order_mismatch_violation` | `order` contains a slot NOT in `active_slots` OR misses active slots | Raises `ValueError` with `active but not ordered` or `ordered but not active` |
| T7 | `test_render_profile_duplicate_order_violation` | `order` contains duplicate slots | Raises `ValueError` |
| T8 | `test_render_profile_frozen` | Attributes are immutable | `FrozenInstanceError` on attribute assignment |
| T9 | `test_render_profile_equality_by_value` | Same fields → equal | `profile_a == profile_b` |
| T10 | `test_render_profile_empty_active_slots` | Empty active_slots + empty order is valid | No exception raised |
| T11 | `test_render_profile_name_in_repr` | Name in repr for debugging | `"test_profile" in repr(profile)` |
| T12 | `test_default_profile_all_slots_active` | `_DEFAULT_PROFILE` has all 12 slots active | `_DEFAULT_PROFILE.active_slots == frozenset(PromptSlot)` |
| T13 | `test_default_profile_order_matches_standard` | `_DEFAULT_PROFILE.order` is the enum definition order | `_DEFAULT_PROFILE.order == tuple(PromptSlot)` |
| T14 | `test_prompt_slot_values_unique` | No two members share a value | `len(set(s.value for s in PromptSlot)) == len(PromptSlot)` |
| T15 | `test_render_profile_single_slot` | Profile with exactly 1 slot is valid | `RenderProfile(name="single", active_slots=frozenset({PromptSlot.INSTRUCTIONS}), order=(PromptSlot.INSTRUCTIONS,))` — no exception |

`tests/unit/core/flow/handlers/test_profiles.py` — policy constants:

| # | Test | Story | Asserts |
|---|------|-------|---------|
| P1 | `test_full_profile_all_slots_active` | FULL includes every slot | `FULL.active_slots == frozenset(PromptSlot)` |
| P2 | `test_full_profile_order_is_standard` | FULL order is the standard sequence | `FULL.order == _STANDARD_ORDER` |
| P3 | `test_minimal_profile_exact_slots` | MINIMAL has exactly 3 slots | `MINIMAL.active_slots == {INSTRUCTIONS, METADATA, TOPOLOGY}` |
| P4 | `test_minimal_profile_order` | MINIMAL order matches its active_slots | All order slots are in active_slots |
| P5 | `test_interactive_excludes_constitution_standards` | INTERACTIVE has all slots EXCEPT CONSTITUTION and STANDARDS | `PromptSlot.CONSTITUTION not in INTERACTIVE.active_slots` and `PromptSlot.STANDARDS not in INTERACTIVE.active_slots` |
| P6 | `test_interactive_includes_agent_memory` | INTERACTIVE includes AGENT_MEMORY (RT-28) | `PromptSlot.AGENT_MEMORY in INTERACTIVE.active_slots` |
| P7 | `test_interactive_slot_count` | INTERACTIVE has exactly 10 slots (12 - 2) | `len(INTERACTIVE.active_slots) == 10` |
| P8 | `test_arbiter_exact_slots` | ARBITER has exactly 2 slots | `ARBITER.active_slots == {INSTRUCTIONS, CONTEXT}` |
| P9 | `test_all_profiles_pass_validation` | All 4 profiles satisfy order == active_slots | No `ValueError` on construction |
| P10 | `test_profiles_are_distinct` | No two profiles are equal | Pairwise inequality |
| P11 | `test_profiles_are_frozen` | All profiles reject mutation | `FrozenInstanceError` on assignment |
| P12 | `test_standard_order_matches_enum_definition` | `_STANDARD_ORDER` matches `tuple(PromptSlot)` | Proves equality to `_DEFAULT_PROFILE` via transitivity without cross-module private imports |
| P13 | `test_full_profile_name` | Profile names are correct for logging | `FULL.name == "FULL"` |

Verification:

```bash
# Run SF-01 unit tests
pytest tests/unit/infrastructure/llm/test_prompt_profiles.py -v
pytest tests/unit/core/flow/handlers/test_profiles.py -v

# Run full existing prompt builder tests (regression)
pytest tests/unit/infrastructure/llm/test_prompt_builder.py -v

# Architecture boundary check
tach check

# Type check new modules
mypy src/specweaver/infrastructure/llm/_prompt_profiles.py --ignore-missing-imports
mypy src/specweaver/core/flow/handlers/_profiles.py --ignore-missing-imports

# Lint
ruff check src/specweaver/infrastructure/llm/_prompt_profiles.py
ruff check src/specweaver/core/flow/handlers/_profiles.py
```

`tach check` passes (no new boundary violations); all existing tests pass (zero regressions).

## As built

**Since moved** (noted 2026-09-25): `_prompt_profiles.py` is now a backward-compatibility facade over
`infrastructure/llm/prompt/profiles.py` (`0cd1ed2f`). Line refs above are as of the plan's date.
