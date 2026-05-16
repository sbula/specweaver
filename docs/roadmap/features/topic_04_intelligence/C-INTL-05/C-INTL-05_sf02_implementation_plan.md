# Implementation Plan: Configurable Prompt Render Profiles [SF-02: Profile-Driven Rendering & Builder Refactoring]

- **Feature ID**: C-INTL-05
- **Sub-Feature**: SF-02 — Profile-Driven Rendering & Builder Refactoring
- **Design Document**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_sf02_implementation_plan.md
- **Status**: DRAFT

## Goal

Refactor `PromptBuilder` and `_prompt_render.py` to use `RenderProfile` for slot filtering and rendering order. Refactor `_build_base_prompt()` signature to accept `profile: RenderProfile`. Ensure backward compatibility (FR-9) via an internal all-slots-active default profile and `DeprecationWarning`.

## FRs Covered

- **FR-4**: Profile-Driven Rendering — `render_blocks()` accepts profile order
- **FR-5**: PromptBuilder Profile Initialization — `profile` param, `_is_slot_active()`, `clone()` propagation, I/O early-return
- **FR-6**: `_build_base_prompt()` Refactoring — replace `include_rules: bool` with `profile: RenderProfile`

## Proposed Changes

### Component 1: Profile-Driven Rendering

#### [MODIFY] [_prompt_render.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/_prompt_render.py)

**Change `render_blocks()` signature** to accept an optional `order` parameter:

```python
def render_blocks(
    blocks: list[_ContentBlock],
    order: tuple[PromptSlot, ...] | None = None,
) -> str:
```

When `order` is provided, iterate over `order` and dispatch each slot to its renderer. When `None`, use the current hardcoded sequence (backward compat).

**Slot rendering dispatch logic** (replaces lines 72-116):

Slots fall into 3 rendering categories:
1. **Tagged blocks** (INSTRUCTIONS, DICTATOR_OVERRIDES, METADATA, CONSTITUTION, STANDARDS, PLAN, AGENT_MEMORY, REMINDER): Use existing `_render_tagged_blocks(blocks, slot.value, slot.value)`
2. **Custom renderers** (TOPOLOGY, FILE, MENTIONED, CONTEXT): Each has dedicated inline rendering logic already present — extract into small helper functions called from the dispatch loop
3. **Unknown slots**: `logger.debug()` and skip

> [!CAUTION]
> **Intentional XML format change (RT-1):** Agent memory blocks will now render as
> `<agent_memory>content</agent_memory>` instead of the previous `<context label="agent_memory">content</context>`.
> This is correct DDD behavior — agent memory IS a distinct slot, not a context subtype.
> The change is intentional and improves prompt clarity for the LLM.

**New helper functions** (extracted from existing inline code):

```python
def _render_topology(blocks: list[_ContentBlock]) -> str | None:
    """Render topology blocks into XML."""
    # Extracted from render_blocks lines 87-92

def _render_contexts(blocks: list[_ContentBlock]) -> str | None:
    """Render context blocks into XML."""
    # Extracted from render_blocks lines 105-110
```

> [!CAUTION]
> **Topology extraction fidelity (RT-14):** `_render_topology()` uses **per-block** rendering
> (one `<topology>` tag per block), NOT the merged pattern used by `_render_tagged_blocks()`.
> The extraction must faithfully reproduce the current inline code. Do NOT switch to the
> merged pattern — it would change the output format.

**Import additions for `_prompt_render.py`** (RT-23):

`PromptSlot` must be imported under the existing `if TYPE_CHECKING:` block (not at runtime)
since `from __future__ import annotations` is already present in the file.

> [!NOTE]
> `render_files()` and `_render_mentioned()` already exist as standalone functions.
> `_render_tagged_blocks()` already exists. No new rendering logic is needed —
> only extraction and dispatch reorganization.

**Dispatch map** (inside `render_blocks`):

```python
_SLOT_RENDERERS: dict[str, Callable] = {
    "topology": _render_topology,
    "file": render_files,
    "mentioned": _render_mentioned,
    "context": _render_contexts,
}
```

Slots NOT in this map use `_render_tagged_blocks(blocks, slot.value, slot.value)`.
This includes REMINDER (which uses the merged tagged-block pattern) and AGENT_MEMORY.
Use `slot.value` for dispatch map lookups to be explicit about the string key type.

> [!NOTE]
> The legacy `ordered_tags` list in the `order is None` fallback path must also include
> `"agent_memory"` for defense-in-depth (RT-3).

> [!CAUTION]
> The `render_blocks()` function MUST remain callable without `order` for backward
> compatibility. Existing callers in `PromptBuilder._render()` will pass `order`
> from the profile; any other direct callers get the legacy path.

---

### Component 2: PromptBuilder Profile Integration

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/prompt_builder.py)

**2a. Constructor** — add `profile` parameter:

```python
def __init__(
    self,
    budget: TokenBudget | None = None,
    adapter: LLMAdapter | None = None,
    *,
    budget_scale_factor: float = 1.0,
    skeleton_files: dict[str, str] | None = None,
    profile: RenderProfile | None = None,
) -> None:
```

When `profile is None`: assign `_DEFAULT_PROFILE` and emit `warnings.warn("PromptBuilder created without explicit profile — using _DEFAULT_PROFILE. Pass a RenderProfile for explicit slot control.", DeprecationWarning, stacklevel=2)`. Store as `self._profile`. This uses the Python-standard `warnings.warn` mechanism so warnings are shown once per callsite and are filterable.

> [!IMPORTANT]
> The deprecation warning fires ONCE per `PromptBuilder()` construction without
> `profile`. This is FR-9. It does NOT change behavior — all slots remain active.

**2b. Slot activity check** — new private method:

```python
def _is_slot_active(self, slot: PromptSlot) -> bool:
    """Check if a slot is active in the current profile."""
    return slot in self._profile.active_slots
```

**2c. Add-method gating** — each `add_*` method checks slot activity before doing work:

| Method | Slot | Has I/O? | Early-return behavior |
|--------|------|----------|----------------------|
| `add_instructions()` | `INSTRUCTIONS` | No | Skip append, `logger.debug` |
| `add_dictator_overrides()` | `DICTATOR_OVERRIDES` | No | Skip append, `logger.debug` |
| `add_file()` | `FILE` | **Yes** (disk read) | **Early-return BEFORE `path.read_text()`** |
| `add_context()` | Caller-specified via new `slot` param | No | Skip append, `logger.debug` |
| `add_project_metadata()` | `METADATA` | No | Skip append, `logger.debug` |
| `add_topology()` | `TOPOLOGY` | No | Skip append, `logger.debug` |
| `add_reminder()` | `REMINDER` | No | Skip append, `logger.debug` |
| `add_constitution()` | `CONSTITUTION` | No | Skip append, `logger.debug` |
| `add_standards()` | `STANDARDS` | No | Skip append, `logger.debug` |
| `add_plan()` | `PLAN` | No | Skip append, `logger.debug` |
| `add_mentioned_files()` | `MENTIONED` | **Yes** (disk read) | **Early-return BEFORE any `read_text()`** |

> [!IMPORTANT]
> **Guard ordering (RT-7):** Methods that have existing None/empty checks (e.g.,
> `add_project_metadata(None)`, `add_topology([])`, `add_mentioned_files([])`) MUST
> preserve those checks BEFORE the slot gate. This ensures backward compatibility
> for callers passing empty data regardless of profile state.

Guard pattern for methods with existing None/empty checks:
```python
def add_project_metadata(self, metadata: ProjectMetadata | None, ...) -> PromptBuilder:
    if not metadata:
        return self  # Existing None-guard — unchanged
    if not self._is_slot_active(PromptSlot.METADATA):
        logger.debug("Slot %s inactive — skipping", PromptSlot.METADATA)
        return self
    # ... existing logic unchanged
```

Guard pattern for simple non-I/O methods:
```python
def add_instructions(self, text: str) -> PromptBuilder:
    if not self._is_slot_active(PromptSlot.INSTRUCTIONS):
        logger.debug("Slot %s inactive — skipping add_instructions", PromptSlot.INSTRUCTIONS)
        return self
    # ... existing logic unchanged
```

Guard pattern for I/O methods (NFR-1 critical):
```python
def add_file(self, path: Path, ...) -> PromptBuilder:
    if not self._is_slot_active(PromptSlot.FILE):
        logger.debug("Slot %s inactive — skipping add_file for %s", PromptSlot.FILE, path)
        return self  # BEFORE any disk I/O
    content = path.read_text(encoding="utf-8")  # I/O happens only after gate
    # ... rest unchanged
```

Guard pattern for `add_mentioned_files` (RT-22):
```python
def add_mentioned_files(self, mentions: list[ResolvedMention], ...) -> PromptBuilder:
    if not mentions:
        return self  # Existing empty-guard — added for consistency
    if not self._is_slot_active(PromptSlot.MENTIONED):
        logger.debug("Slot %s inactive — skipping", PromptSlot.MENTIONED)
        return self  # BEFORE any disk I/O
    # ... existing logic unchanged
```

**2d. `add_context()` slot parameter** — add optional `slot` kwarg:

```python
def add_context(
    self,
    text: str,
    label: str,
    *,
    priority: int = 3,
    slot: PromptSlot = PromptSlot.CONTEXT,
) -> PromptBuilder:
```

When `slot` is provided, the gate checks that slot. The `_ContentBlock.kind` is set to `slot.value` instead of hardcoded `"context"`. This enables `_build_base_prompt()` to inject agent memory as `slot=PromptSlot.AGENT_MEMORY` with `kind="agent_memory"` so the profile system can filter it correctly.

> [!WARNING]
> The `add_context(slot=...)` change means that `_build_base_prompt()` memory hydration
> (base.py:219) MUST change from `builder.add_context(block, "agent_memory", priority=2)`
> to `builder.add_context(block, "agent_memory", priority=2, slot=PromptSlot.AGENT_MEMORY)`.
> This is part of the FR-6 refactoring in Component 3.

**2e. `clone()` propagation**:

```python
def clone(self) -> PromptBuilder:
    builder = PromptBuilder(
        budget=self._budget,
        adapter=self._adapter,
        budget_scale_factor=1.0,
        skeleton_files=self._skeleton_files.copy() if self._skeleton_files else None,
        profile=self._profile,  # NEW: propagate profile
    )
    builder._scale = self._scale
    builder._auto_scale = self._auto_scale
    builder._blocks = copy.deepcopy(self._blocks)
    return builder
```

**2f. `_render()` passes profile order**:

```python
def _render(self, blocks: list[_ContentBlock]) -> str:
    from specweaver.infrastructure.llm._prompt_render import render_blocks
    return render_blocks(blocks, order=self._profile.order)
```

---

### Component 3: `_build_base_prompt()` Refactoring

#### [MODIFY] [base.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers/base.py)

**Signature change** (FR-6):

```python
async def _build_base_prompt(
    context: RunContext,
    instructions: str,
    *,
    profile: RenderProfile | None = None,
    include_rules: bool = True,       # DEPRECATED — kept for backward compat
    skeleton_files: dict[str, str] | None = None,
) -> PromptBuilder:
```

**Profile resolution logic** (single control plane — RT-2, RT-16):

```python
import warnings
from specweaver.infrastructure.llm._prompt_profiles import PromptSlot, RenderProfile
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder
from specweaver.core.flow.handlers._profiles import FULL, INTERACTIVE

# 1. Resolve profile from arguments
if profile is not None and include_rules != True:
    # RT-13: Both passed with conflicting intent — warn, profile wins
    warnings.warn(
        f"Both profile and include_rules were passed. "
        f"Profile '{profile.name}' takes precedence. "
        f"include_rules is deprecated.",
        DeprecationWarning, stacklevel=2,
    )
elif profile is None:
    # RT-2: Map legacy boolean to policy profile
    if include_rules:
        profile = FULL
    else:
        warnings.warn(
            "include_rules is deprecated — use profile=INTERACTIVE",
            DeprecationWarning, stacklevel=2,
        )
        profile = INTERACTIVE

# 2. Build with resolved profile (RT-17: preserve skeleton_files)
builder = PromptBuilder(profile=profile, skeleton_files=skeleton_files)
```

> [!CAUTION]
> **Architecture boundary (RT-16):** `base.py` MUST NOT import `_DEFAULT_PROFILE` from
> `infrastructure/llm/_prompt_profiles.py` — it is explicitly marked as infrastructure-internal.
> Instead, `base.py` resolves `None` profiles using its own policy constants (`FULL`, `INTERACTIVE`)
> from `core/flow/handlers/_profiles.py`. This preserves the Mechanism/Policy DDD boundary.

> [!CAUTION]
> The `include_rules` parameter is kept but deprecated (via `warnings.warn`).
> It will be removed in SF-03 when all callers are migrated to explicit profiles.

**Conditional rule gating refactoring**:

The old `if include_rules:` conditional branch is **completely removed**. The profile's `active_slots` is the sole control mechanism. `_build_base_prompt` now unconditionally calls `add_constitution()` and `add_standards()` — the builder's slot gate handles filtering via `_is_slot_active()`.

**Memory hydration** (slot fix + I/O gating):

```python
# NFR-1: Skip expensive DB round-trip when profile excludes AGENT_MEMORY
if PromptSlot.AGENT_MEMORY in profile.active_slots:
    if context.db is not None and context.project_path is not None:
        # ... perform DB hydration
        builder.add_context(block, "agent_memory", priority=2, slot=PromptSlot.AGENT_MEMORY)
```

---

## Commit Boundaries

### CB-1: Profile-Driven Rendering & Builder Refactoring

**Files modified:**
- `src/specweaver/infrastructure/llm/_prompt_render.py`
- `src/specweaver/infrastructure/llm/prompt_builder.py`
- `src/specweaver/core/flow/handlers/base.py`

**Files created:**
- `tests/unit/infrastructure/llm/test_prompt_builder_profiles.py`
- `tests/unit/infrastructure/llm/test_prompt_render_profiles.py`
- `tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py`

**Commit message:**
`feat(C-INTL-05/SF-02): profile-driven rendering and builder refactoring`

---

## TDD Test Matrix

### Test File 1: `tests/unit/infrastructure/llm/test_prompt_render_profiles.py`

| # | Test | Story | Asserts |
|---|------|-------|---------|
| R1 | `test_render_blocks_with_order_respects_sequence` | Profile order controls rendering sequence | `render_blocks(blocks, order=(CONSTITUTION, INSTRUCTIONS))` renders constitution before instructions |
| R2 | `test_render_blocks_without_order_uses_legacy` | No order → current hardcoded sequence | Output identical to current `render_blocks(blocks)` |
| R3 | `test_render_blocks_skips_empty_slots` | Slots in order with no matching blocks → no empty tags | No `<topology>` tag when no topology blocks exist |
| R4 | `test_render_topology_extracted_helper` | `_render_topology()` produces same output as inline code — per-block pattern preserved | Compare with known good output |
| R5 | `test_render_contexts_extracted_helper` | `_render_contexts()` produces same output | Compare with known good output |
| R6 | `test_render_blocks_reminder_via_tagged_blocks` | REMINDER routed through `_render_tagged_blocks` (not custom renderer) | `<reminder>content</reminder>` present |
| R7 | `test_render_blocks_agent_memory_uses_tagged_renderer` | Block with `kind="agent_memory"` renders as `<agent_memory>` not `<context label="...">` | `<agent_memory>` tag present, no `<context label="agent_memory">` |

### Test File 2: `tests/unit/infrastructure/llm/test_prompt_builder_profiles.py`

| # | Test | Story | Asserts |
|---|------|-------|---------|
| B1 | `test_builder_no_profile_uses_default` | `PromptBuilder()` without profile uses `_DEFAULT_PROFILE` | `builder._profile == _DEFAULT_PROFILE` |
| B2 | `test_builder_no_profile_emits_deprecation_warning` | No profile → `DeprecationWarning` emitted | `pytest.warns(DeprecationWarning)` captures warning |
| B3 | `test_builder_explicit_profile_no_warning` | `PromptBuilder(profile=FULL)` → no warning | No `DeprecationWarning` emitted |
| B4 | `test_inactive_slot_skips_add_instructions` | ARBITER profile → `add_constitution()` is no-op | No `<constitution>` in output |
| B5 | `test_inactive_slot_skips_add_file_before_io` | ARBITER profile → `add_file()` does not read disk | Mock `path.read_text` never called |
| B6 | `test_inactive_slot_skips_add_mentioned_before_io` | MINIMAL profile → `add_mentioned_files()` does not read disk | Mock `read_text` never called |
| B7 | `test_active_slot_allows_add` | FULL profile → `add_constitution()` works normally | `<constitution>` in output |
| B8 | `test_clone_preserves_profile` | `clone()` copies profile to new instance | `cloned._profile is original._profile` |
| B9 | `test_add_context_with_slot_sets_kind` | `add_context("x", "mem", slot=AGENT_MEMORY)` → block.kind == "agent_memory" | Block kind matches slot value |
| B10 | `test_add_context_default_slot_is_context` | `add_context("x", "label")` → block.kind == "context" | Backward compatible |
| B11 | `test_profile_controls_render_order` | ARBITER profile → instructions before context, no other slots | Output matches expected order |
| B12 | `test_full_profile_backward_compatible_output` | `PromptBuilder(profile=FULL)` produces identical output to `PromptBuilder()` for same blocks | String equality |
| B13 | `test_is_slot_active_returns_correct` | `_is_slot_active(CONSTITUTION)` on ARBITER → False | Direct method check |

### Test File 3: `tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py`

| # | Test | Story | Asserts |
|---|------|-------|---------|
| H1 | `test_build_base_prompt_with_profile_full` | `profile=FULL` → includes constitution, standards, memory | All blocks present |
| H2 | `test_build_base_prompt_with_profile_interactive` | `profile=INTERACTIVE` → excludes constitution/standards, includes memory | No `<constitution>`, has memory |
| H3 | `test_build_base_prompt_with_profile_arbiter` | `profile=ARBITER` → only instructions + context | No constitution, no standards, no metadata |
| H4 | `test_build_base_prompt_with_profile_minimal` | `profile=MINIMAL` → only instructions + metadata + topology | No constitution, no standards, no memory |
| H5 | `test_build_base_prompt_deprecated_include_rules` | `include_rules=False` without profile → still works, emits `DeprecationWarning` | `pytest.warns(DeprecationWarning)`, backward compatible |
| H6 | `test_build_base_prompt_profile_overrides_include_rules` | Both `profile` and `include_rules=False` passed → profile wins, `DeprecationWarning` emitted | Profile behavior observed, warning captured |
| H7 | `test_build_base_prompt_memory_skipped_when_slot_inactive` | `profile=MINIMAL` → memory hydration DB call never made | Mock DB `async_session_scope` not called |
| H8 | `test_build_base_prompt_memory_hydrated_when_slot_active` | `profile=FULL` + DB available → agent_memory block has correct kind | `kind == "agent_memory"` not `"context"` |
| H9 | `test_build_base_prompt_memory_slot_active_but_db_none` | `profile=FULL` but `context.db=None` → no memory block, no error | No `agent_memory` tag in output, no exception |

### Integration Tests (in existing files — extend)

| # | Test | File | Story |
|---|------|------|-------|
| I1 | `test_profile_truncation_minimal_tight_budget` | `test_prompt_builder_profiles.py` | MINIMAL profile under tight budget → only 3 slots compete for space |
| I2 | `test_profile_truncation_full_priority_dropping` | `test_prompt_builder_profiles.py` | FULL profile under tight budget → low-priority slots dropped first |

> [!NOTE]
> **Fixture reuse (RT-15):** `test_build_base_prompt_profiles.py` should reuse the
> `mock_db` and `run_context` fixtures from the existing `conftest.py` in
> `tests/unit/core/flow/handlers/`.

---

## Research Notes

### Phase 0 Synthesis

1. **Current `render_blocks()` hardcoded order** (lines 73-116): `instructions → dictator-overrides → project_metadata → constitution → standards → plan → topology → file → mentioned → context → reminder`. This exactly matches `_STANDARD_ORDER` in `_profiles.py` and `tuple(PromptSlot)` in `_prompt_profiles.py`. Confirmed by test P12.

2. **`_ContentBlock.kind` field** (line 54-55): Currently a plain `str`. SF-02 does NOT change this to `PromptSlot` — that would be a breaking change across all existing tests. Instead, the slot gate compares `slot.value` (str) with the block's `kind` (str). The `PromptSlot` is a `StrEnum`, so `slot == block.kind` works directly.

3. **`add_context()` currently uses `kind="context"` for everything** including agent memory (base.py:219). The new `slot` parameter allows callers to set `kind=slot.value` so the rendering dispatch can distinguish `context` from `agent_memory` blocks.

4. **`clone()` currently does NOT propagate profile** (lines 89-103). Must add `profile=self._profile` to the constructor call.

5. **Existing test count**: 869 lines in `test_prompt_builder.py`, 150 lines in `test_prompt_profiles.py`, 88 lines in `test_profiles.py`, 194 lines in `test_build_base_prompt.py`. All must continue passing (NFR-4).

6. **`_build_base_prompt()` has 7 callers** (grep confirmed): `draft.py:80`, `generation.py:150`, `generation.py:252`, `generation.py:445`, `review.py:162`, `review.py:273`. All currently use `include_rules=True` (default) except `draft.py:83` which uses `include_rules=False`. SF-02 keeps `include_rules` working but deprecated. SF-03 migrates all callers.

7. **No new external dependencies**. All changes use stdlib + existing Pydantic.

8. **Import chain safety**: `prompt_builder.py` will import from `_prompt_profiles.py` (same package — legal). `base.py` will import from `_prompt_profiles.py` (flow → llm — legal per flow's `context.yaml` `consumes: specweaver/llm`).

---

## Verification Plan

### Automated Tests

```bash
# New SF-02 tests
pytest tests/unit/infrastructure/llm/test_prompt_render_profiles.py -v
pytest tests/unit/infrastructure/llm/test_prompt_builder_profiles.py -v
pytest tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py -v

# Regression — all existing prompt tests MUST still pass
pytest tests/unit/infrastructure/llm/test_prompt_builder.py -v
pytest tests/unit/infrastructure/llm/test_prompt_profiles.py -v
pytest tests/unit/core/flow/handlers/test_profiles.py -v
pytest tests/unit/core/flow/handlers/test_build_base_prompt.py -v

# Architecture boundary check
tach check

# Type check modified modules
mypy src/specweaver/infrastructure/llm/_prompt_render.py --ignore-missing-imports
mypy src/specweaver/infrastructure/llm/prompt_builder.py --ignore-missing-imports
mypy src/specweaver/core/flow/handlers/base.py --ignore-missing-imports

# Lint
ruff check src/specweaver/infrastructure/llm/_prompt_render.py
ruff check src/specweaver/infrastructure/llm/prompt_builder.py
ruff check src/specweaver/core/flow/handlers/base.py
```

### Manual Verification
- Confirm `tach check` passes (no new boundary violations)
- Confirm all existing tests pass (zero regressions from SF-02)
- Confirm deprecation warning appears when `PromptBuilder()` is called without `profile`
