# Implementation Plan: Configurable Prompt Render Profiles [SF-01: Slot Registry & Profile Mechanism]

- **Feature ID**: C-INTL-05
- **Sub-Feature**: SF-01 — Slot Registry & Profile Mechanism
- **Design Document**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_sf01_implementation_plan.md
- **Status**: COMPLETE

## Goal

Define the `PromptSlot` str Enum and `RenderProfile` frozen dataclass as domain-agnostic
mechanism types in `infrastructure/llm/_prompt_profiles.py`. Define the 4 named profile
constants (`FULL`, `MINIMAL`, `INTERACTIVE`, `ARBITER`) as orchestration policy in
`core/flow/handlers/_profiles.py`. Update `infrastructure/llm/context.yaml` to expose the
new types. Ensure backward compatibility via FR-9.

## FRs Covered

- **FR-1**: PromptSlot str Enum Registry
- **FR-2**: RenderProfile frozen dataclass mechanism
- **FR-3**: Named profile constants (policy)
- **FR-9**: Backward compatibility (anonymous default profile)

## Proposed Changes

### Component 1: Infrastructure Mechanism Types

#### [NEW] [_prompt_profiles.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/_prompt_profiles.py)

New private module in `infrastructure/llm/`. Follows the naming convention of existing
private modules in this package (`_prompt_constants.py`, `_prompt_render.py`).

**`PromptSlot` — str Enum (AD-2)**

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

> [!NOTE]
> `AGENT_MEMORY` is a forward-looking slot for B-INTL-09 Agent Memory Bank hydration.
> It is not used in SF-01 but is declared here so that profile definitions can reference
> it without requiring an enum extension later. Current `_build_base_prompt` memory
> hydration uses `kind="context"` with `label="agent_memory"` — SF-02 will migrate this
> to the dedicated slot.

**`RenderProfile` — Frozen Dataclass (AD-3)**

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

> [!CAUTION]
> **Validation uses `ValueError`, not `assert`** — per Python best practices,
> `assert` can be disabled with `-O`. Runtime invariant violations must be
> hard errors.

---

#### [MODIFY] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/context.yaml)

Add `PromptSlot` and `RenderProfile` to the `exposes` list (NFR-2 / RT-27):

```diff
 exposes:
   - LLMAdapter
   ...
   - wrap_artifact_tag
+  - PromptSlot
+  - RenderProfile
```

---

### Component 2: Orchestration Policy Constants

#### [NEW] [_profiles.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers/_profiles.py)

New private module in `core/flow/handlers/`. This module imports `PromptSlot` and
`RenderProfile` from `infrastructure/llm/_prompt_profiles` — a legal dependency since
`flow` already `consumes: specweaver/llm` in its `context.yaml`.

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

> [!IMPORTANT]
> **`_STANDARD_ORDER` defines the backward-compatible rendering sequence.**
> This tuple mirrors the exact order from `_prompt_render.py:73-116`:
> instructions → dictator-overrides → project_metadata → constitution → standards →
> plan → topology → file → mentioned → context → agent_memory → reminder.
> SF-02 will use this to replace the hardcoded `ordered_tags` list.

---

### Component 3: Backward Compatibility Shim (FR-9)

This is a design-only component for SF-01. The actual implementation of the deprecation
warning and anonymous default profile is deferred to **SF-02** when `PromptBuilder.__init__`
is modified to accept the `profile` parameter.

For SF-01, we define the `_DEFAULT_PROFILE` constant that SF-02 will use:

In `_prompt_profiles.py`, add at the bottom:

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

> [!NOTE]
> The anonymous default has ALL slots active with the enum definition order.
> This guarantees `PromptBuilder()` without a profile produces identical output
> to the current behavior (NFR-4). The `order` uses enum definition order which
> matches the current hardcoded tag sequence in `_prompt_render.py`.

> [!WARNING]
> `_DEFAULT_PROFILE` uses `tuple(PromptSlot)` for its order, which is the enum
> member definition order. **This must match `_STANDARD_ORDER` exactly.** The
> enum member order in `PromptSlot` is therefore load-bearing and must not be
> reordered casually. Both orderings are tested for equality in the test suite.

---

## Commit Boundaries

### CB-1: Mechanism Types + Policy Constants + Tests

**Files created:**
- `src/specweaver/infrastructure/llm/_prompt_profiles.py`
- `src/specweaver/core/flow/handlers/_profiles.py`
- `tests/unit/infrastructure/llm/test_prompt_profiles.py`
- `tests/unit/core/flow/handlers/test_profiles.py`

**Files modified:**
- `src/specweaver/infrastructure/llm/context.yaml` (add `PromptSlot`, `RenderProfile` to `exposes`)

**Commit message:**
`feat(C-INTL-05/SF-01): add PromptSlot enum and RenderProfile dataclass`

---

## TDD Test Matrix

### Test File 1: `tests/unit/infrastructure/llm/test_prompt_profiles.py`

Tests for the mechanism types (`PromptSlot`, `RenderProfile`, `_DEFAULT_PROFILE`).

| # | Test | Story | Asserts |
|---|------|-------|---------|
| T1 | `test_prompt_slot_is_str_enum` | `PromptSlot` members are string values | `isinstance(PromptSlot.INSTRUCTIONS, str)` and `PromptSlot.INSTRUCTIONS == "instructions"` |
| T2 | `test_prompt_slot_all_11_base_kinds_present` | Enum covers all 11 existing `_ContentBlock.kind` values | Each of `instructions`, `dictator-overrides`, `project_metadata`, `constitution`, `standards`, `plan`, `topology`, `file`, `mentioned`, `context`, `reminder` has a corresponding `PromptSlot` member |
| T3 | `test_prompt_slot_agent_memory_present` | Forward-looking slot exists | `PromptSlot.AGENT_MEMORY == "agent_memory"` |
| T4 | `test_prompt_slot_total_count` | Exactly 12 members | `len(PromptSlot) == 12` |
| T5 | `test_render_profile_creation_valid` | Happy path: valid profile with order exactly matching active_slots | No exception raised |
| T6 | `test_render_profile_order_mismatch_violation` | `order` contains slot NOT in `active_slots` OR misses active slots | Raises `ValueError` with descriptive message including `active but not ordered` or `ordered but not active` |
| T7 | `test_render_profile_duplicate_order_violation` | `order` contains duplicate slots | Raises `ValueError` |
| T8 | `test_render_profile_frozen` | Profile attributes are immutable | `FrozenInstanceError` on attribute assignment |
| T9 | `test_render_profile_equality_by_value` | Two profiles with same fields are equal | `profile_a == profile_b` |
| T10 | `test_render_profile_empty_active_slots` | Empty active_slots + empty order is valid | No exception raised |
| T11 | `test_render_profile_name_in_repr` | Name appears in repr for debugging | `"test_profile" in repr(profile)` |
| T12 | `test_default_profile_all_slots_active` | `_DEFAULT_PROFILE` has all 12 slots active | `_DEFAULT_PROFILE.active_slots == frozenset(PromptSlot)` |
| T13 | `test_default_profile_order_matches_standard` | `_DEFAULT_PROFILE.order` matches the enum definition order | `_DEFAULT_PROFILE.order == tuple(PromptSlot)` |
| T14 | `test_prompt_slot_values_unique` | No two enum members share the same string value | `len(set(s.value for s in PromptSlot)) == len(PromptSlot)` |
| T15 | `test_render_profile_single_slot` | Profile with exactly 1 slot is valid | `RenderProfile(name="single", active_slots=frozenset({PromptSlot.INSTRUCTIONS}), order=(PromptSlot.INSTRUCTIONS,))` — no exception |

### Test File 2: `tests/unit/core/flow/handlers/test_profiles.py`

Tests for the policy constants (`FULL`, `MINIMAL`, `INTERACTIVE`, `ARBITER`).

| # | Test | Story | Asserts |
|---|------|-------|---------|
| P1 | `test_full_profile_all_slots_active` | FULL includes every slot | `FULL.active_slots == frozenset(PromptSlot)` |
| P2 | `test_full_profile_order_is_standard` | FULL ordering matches the standard sequence | `FULL.order == _STANDARD_ORDER` |
| P3 | `test_minimal_profile_exact_slots` | MINIMAL has exactly 3 slots | `MINIMAL.active_slots == {INSTRUCTIONS, METADATA, TOPOLOGY}` |
| P4 | `test_minimal_profile_order` | MINIMAL order matches its active_slots | All order slots are in active_slots |
| P5 | `test_interactive_excludes_constitution_standards` | INTERACTIVE has all slots EXCEPT CONSTITUTION and STANDARDS | `PromptSlot.CONSTITUTION not in INTERACTIVE.active_slots` and `PromptSlot.STANDARDS not in INTERACTIVE.active_slots` |
| P6 | `test_interactive_includes_agent_memory` | INTERACTIVE includes AGENT_MEMORY (RT-28 fix) | `PromptSlot.AGENT_MEMORY in INTERACTIVE.active_slots` |
| P7 | `test_interactive_slot_count` | INTERACTIVE has exactly 10 slots (12 - 2) | `len(INTERACTIVE.active_slots) == 10` |
| P8 | `test_arbiter_exact_slots` | ARBITER has exactly 2 slots | `ARBITER.active_slots == {INSTRUCTIONS, CONTEXT}` |
| P9 | `test_all_profiles_pass_validation` | All 4 profiles satisfy the order == active_slots invariant | No `ValueError` on construction |
| P10 | `test_profiles_are_distinct` | No two profiles are equal | Pairwise inequality |
| P11 | `test_profiles_are_frozen` | All profiles reject attribute mutation | `FrozenInstanceError` on assignment |
| P12 | `test_standard_order_matches_enum_definition` | `_STANDARD_ORDER` matches `tuple(PromptSlot)` | Proves equality to `_DEFAULT_PROFILE` via transitivity without cross-module private imports |
| P13 | `test_full_profile_name` | Profile names are correct for logging | `FULL.name == "FULL"` |

---

## Research Notes

### Phase 0 Synthesis

1. **`StrEnum` (Python 3.11+)**: Python 3.13 is used (confirmed in `pyproject.toml`).
   `StrEnum` is stdlib since 3.11 — no need for `str, Enum` inheritance hack.
   Import: `from enum import StrEnum`.

2. **Frozen dataclass `__post_init__`**: Use `ValueError` (not `assert`) for validation.
   Use `object.__setattr__` if normalization is needed. Our `RenderProfile` only validates
   (no normalization), so standard `__post_init__` is sufficient.

3. **Existing `kind` values**: The current `_ContentBlock` uses 11 string values for `kind`:
   `instructions`, `dictator-overrides`, `project_metadata`, `constitution`, `standards`,
   `plan`, `topology`, `file`, `mentioned`, `context`, `reminder`. Each maps 1:1 to a
   `PromptSlot` member.

4. **`context.yaml` exports**: `infrastructure/llm/context.yaml` must add `PromptSlot`
   and `RenderProfile` to `exposes`. Without this, imports from `core/flow/` would be
   an undeclared boundary crossing (RT-27).

5. **No `__init__.py`**: The `llm/` module uses PEP-420 implicit namespace packaging.
   The new `_prompt_profiles.py` is consumed directly by path — no `__init__.py` updates.

6. **`tach.toml`**: Boundary enforcement operates at `src.specweaver.infrastructure.llm`
   level. Both `_prompt_profiles.py` (infra) and `_profiles.py` (flow/handlers) are within
   their respective boundary zones. The import direction is: `flow → llm` (legal, declared
   in flow's `context.yaml` `consumes: specweaver/llm`).

7. **Test patterns**: Existing tests use `pytest` with `@pytest.mark.parametrize`, class-based
   grouping, and `tmp_path` fixtures. New tests follow the same conventions. Test file
   placement mirrors source structure: `tests/unit/infrastructure/llm/` and
   `tests/unit/core/flow/handlers/`.

---

## Verification Plan

### Automated Tests

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

### Manual Verification
- Confirm `tach check` passes (no new boundary violations introduced)
- Confirm all existing tests still pass (zero regressions from SF-01)
