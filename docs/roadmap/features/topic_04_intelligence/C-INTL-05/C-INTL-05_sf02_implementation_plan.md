# C-INTL-05 SF-02 — Profile-Driven Rendering & Builder Refactoring

**Status**: DRAFT (never re-marked; SF-02 shipped in `62d32051`, 2026-05-13) · **FRs owned**: FR-4,
FR-5, FR-6 · **Depends on**: SF-01 · Design: [C-INTL-05_design.md](C-INTL-05_design.md) §Sub-features → SF-02

## Goal

`PromptBuilder` and `_prompt_render.py` use `RenderProfile` for slot filtering and render order.
`_build_base_prompt()` accepts `profile: RenderProfile`. Backward compatibility (FR-9) via the
internal all-slots-active default and a `DeprecationWarning`.

- **FR-4**: `render_blocks()` accepts the profile order
- **FR-5**: `profile` param, `_is_slot_active()`, `clone()` propagation, I/O early-return
- **FR-6**: replace `include_rules: bool` with `profile: RenderProfile`

## Where it plugs in

| Fact | Where |
|---|---|
| Hardcoded order: 6 ordered tags, then inline `topology`, `file`, `mentioned`, `context`, `reminder`. Full sequence `instructions → dictator-overrides → project_metadata → constitution → standards → plan → topology → file → mentioned → context → reminder` — equals `_STANDARD_ORDER` and `tuple(PromptSlot)` (test P12) | `_prompt_render.py:73-80` (tags); sequence spans lines 73-116; the rewrite replaces lines 72-116 |
| `_render_tagged_blocks()` — generic, already parameterized by `kind`/`tag` | `_prompt_render.py:35-46` |
| `render_files()` / `_render_mentioned()` — already standalone | `_prompt_render.py:17-64` |
| Topology inline render; context inline render | `render_blocks` lines 87-92; 105-110 |
| `_ContentBlock` — `kind` is a plain `str` (lines 54-55) | `prompt_builder.py:47-61` |
| `PromptBuilder.clone()` — does NOT propagate a profile | `prompt_builder.py:89-103` |
| Hybrid priority-based truncation — profile-agnostic, reused as is | `prompt_builder.py:501-599` |
| `_build_base_prompt()`; memory hydration is `add_context(..., kind="context")` at base.py:219 | `core/flow/handlers/base.py:174-232` |
| 7 callers (grep): `draft.py:80`, `generation.py:150`, `generation.py:252`, `generation.py:445`, `review.py:162`, `review.py:273` — all default `include_rules=True` except `draft.py:83` (`include_rules=False`) | handlers |

`_ContentBlock.kind` stays `str` — typing it `PromptSlot` would break every existing test. The gate
compares `slot.value` with `kind`; `PromptSlot` is a `StrEnum`, so `slot == block.kind` works.

Imports: `prompt_builder.py` → `_prompt_profiles.py` (same package); `base.py` → `_prompt_profiles.py`
(flow → llm, legal per flow's `context.yaml` `consumes: specweaver/llm`). No new external
dependencies (stdlib + existing Pydantic).

Regression base (NFR-4, all must keep passing): 869 lines in `test_prompt_builder.py`, 150 in
`test_prompt_profiles.py`, 88 in `test_profiles.py`, 194 in `test_build_base_prompt.py`.

## Changes

### 1. Profile-driven rendering · `src/specweaver/infrastructure/llm/_prompt_render.py`

`render_blocks()` takes an optional `order`:

```python
def render_blocks(
    blocks: list[_ContentBlock],
    order: tuple[PromptSlot, ...] | None = None,
) -> str:
```

With `order`: iterate it and dispatch each slot. With `order is None`: the legacy hardcoded sequence — and
`render_blocks()` MUST stay callable without `order`. `PromptBuilder._render()` passes the profile's
order; any other direct caller gets the legacy path. The legacy `ordered_tags` list also includes
`"agent_memory"` (defense-in-depth, RT-3).

Three slot categories:

1. **Tagged blocks** (INSTRUCTIONS, DICTATOR_OVERRIDES, METADATA, CONSTITUTION, STANDARDS, PLAN,
   AGENT_MEMORY, REMINDER): existing `_render_tagged_blocks(blocks, slot.value, slot.value)`
2. **Custom renderers** (TOPOLOGY, FILE, MENTIONED, CONTEXT): existing inline logic extracted into
   small helpers
3. **Unknown slots**: `logger.debug()` and skip

No new rendering logic — only extraction and dispatch:

```python
def _render_topology(blocks: list[_ContentBlock]) -> str | None:
    """Render topology blocks into XML."""
    # Extracted from render_blocks lines 87-92

def _render_contexts(blocks: list[_ContentBlock]) -> str | None:
    """Render context blocks into XML."""
    # Extracted from render_blocks lines 105-110
```

```python
_SLOT_RENDERERS: dict[str, Callable] = {
    "topology": _render_topology,
    "file": render_files,
    "mentioned": _render_mentioned,
    "context": _render_contexts,
}
```

Slots NOT in the map (incl. REMINDER — merged tagged-block pattern — and AGENT_MEMORY) use
`_render_tagged_blocks(blocks, slot.value, slot.value)`. Look up by `slot.value` to be explicit about
the string key type.

> [!CAUTION]
> **Topology fidelity (RT-14):** `_render_topology()` renders **per block** (one `<topology>` tag per
> block), NOT the merged pattern of `_render_tagged_blocks()`. Switching would change the output.

> [!CAUTION]
> **Intentional XML format change (RT-1):** agent memory renders as
> `<agent_memory>content</agent_memory>` instead of `<context label="agent_memory">content</context>`.
> Agent memory IS a distinct slot, not a context subtype; the tag is clearer to the LLM.

`PromptSlot` is imported under the existing `if TYPE_CHECKING:` block (RT-23) —
`from __future__ import annotations` is already present.

### 2. `PromptBuilder` · `src/specweaver/infrastructure/llm/prompt_builder.py`

**2a. Constructor** — add `profile`:

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

`profile is None` → assign `_DEFAULT_PROFILE` and
`warnings.warn("PromptBuilder created without explicit profile — using _DEFAULT_PROFILE. Pass a RenderProfile for explicit slot control.", DeprecationWarning, stacklevel=2)`.
Store as `self._profile`. `warnings.warn` shows once per callsite and is filterable. It fires on each
`PromptBuilder()` without `profile` (FR-9) and changes no behavior — all slots stay active.

**2b. Slot check:**

```python
def _is_slot_active(self, slot: PromptSlot) -> bool:
    """Check if a slot is active in the current profile."""
    return slot in self._profile.active_slots
```

**2c. Add-method gating:**

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
> **Guard ordering (RT-7):** existing None/empty checks (`add_project_metadata(None)`,
> `add_topology([])`, `add_mentioned_files([])`) stay BEFORE the slot gate, so empty data behaves the
> same under any profile.

Existing None/empty check:
```python
def add_project_metadata(self, metadata: ProjectMetadata | None, ...) -> PromptBuilder:
    if not metadata:
        return self  # Existing None-guard — unchanged
    if not self._is_slot_active(PromptSlot.METADATA):
        logger.debug("Slot %s inactive — skipping", PromptSlot.METADATA)
        return self
    # ... existing logic unchanged
```

Simple non-I/O method:
```python
def add_instructions(self, text: str) -> PromptBuilder:
    if not self._is_slot_active(PromptSlot.INSTRUCTIONS):
        logger.debug("Slot %s inactive — skipping add_instructions", PromptSlot.INSTRUCTIONS)
        return self
    # ... existing logic unchanged
```

I/O method (NFR-1 critical):
```python
def add_file(self, path: Path, ...) -> PromptBuilder:
    if not self._is_slot_active(PromptSlot.FILE):
        logger.debug("Slot %s inactive — skipping add_file for %s", PromptSlot.FILE, path)
        return self  # BEFORE any disk I/O
    content = path.read_text(encoding="utf-8")  # I/O happens only after gate
    # ... rest unchanged
```

`add_mentioned_files` (RT-22):
```python
def add_mentioned_files(self, mentions: list[ResolvedMention], ...) -> PromptBuilder:
    if not mentions:
        return self  # Existing empty-guard — added for consistency
    if not self._is_slot_active(PromptSlot.MENTIONED):
        logger.debug("Slot %s inactive — skipping", PromptSlot.MENTIONED)
        return self  # BEFORE any disk I/O
    # ... existing logic unchanged
```

**2d. `add_context()` gets a `slot` kwarg:**

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

The gate checks that slot, and `_ContentBlock.kind` becomes `slot.value` (`kind=slot.value`) instead
of hardcoded `"context"`. So `_build_base_prompt()` injects memory as `slot=PromptSlot.AGENT_MEMORY`
(`kind="agent_memory"`) and the profile can filter it. The hydration call (base.py:219) changes from
`builder.add_context(block, "agent_memory", priority=2)` to
`builder.add_context(block, "agent_memory", priority=2, slot=PromptSlot.AGENT_MEMORY)` — this `add_context(slot=...)` change is part of FR-6.

**2e. `clone()` propagates the profile:**

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

**2f. `_render()` passes the order:**

```python
def _render(self, blocks: list[_ContentBlock]) -> str:
    from specweaver.infrastructure.llm._prompt_render import render_blocks
    return render_blocks(blocks, order=self._profile.order)
```

### 3. `_build_base_prompt()` · `src/specweaver/core/flow/handlers/base.py` (FR-6)

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

Profile resolution — one control plane (RT-2, RT-16):

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
> **Boundary (RT-16):** `base.py` MUST NOT import `_DEFAULT_PROFILE` (infrastructure-internal). It
> resolves `None` with its own policy constants (`FULL`, `INTERACTIVE`) from
> `core/flow/handlers/_profiles.py`, preserving the Mechanism/Policy boundary.

`include_rules` stays, deprecated via `warnings.warn`, until SF-03 migrates every caller and removes it.

The `if include_rules:` branch is **removed**. `_build_base_prompt` calls `add_constitution()` and
`add_standards()` unconditionally; `_is_slot_active()` filters. `active_slots` is the sole control.

Memory hydration — slot fix + I/O gate:

```python
# NFR-1: Skip expensive DB round-trip when profile excludes AGENT_MEMORY
if PromptSlot.AGENT_MEMORY in profile.active_slots:
    if context.db is not None and context.project_path is not None:
        # ... perform DB hydration
        builder.add_context(block, "agent_memory", priority=2, slot=PromptSlot.AGENT_MEMORY)
```

| File | Change | FR |
|---|---|---|
| `src/specweaver/infrastructure/llm/_prompt_render.py` | `order` param, dispatch map, extracted helpers | FR-4 |
| `src/specweaver/infrastructure/llm/prompt_builder.py` | `profile`, gating, `add_context(slot=)`, `clone()`, `_render()` | FR-5 |
| `src/specweaver/core/flow/handlers/base.py` | `profile` param, resolution, unconditional rule adds, gated memory | FR-6 |
| `tests/unit/infrastructure/llm/test_prompt_builder_profiles.py` | NEW | |
| `tests/unit/infrastructure/llm/test_prompt_render_profiles.py` | NEW | |
| `tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py` | NEW | |

Commit boundary CB-1: `feat(C-INTL-05/SF-02): profile-driven rendering and builder refactoring`

## Tests

`tests/unit/infrastructure/llm/test_prompt_render_profiles.py`:

| # | Test | Story | Asserts |
|---|------|-------|---------|
| R1 | `test_render_blocks_with_order_respects_sequence` | Profile order controls sequence | `render_blocks(blocks, order=(CONSTITUTION, INSTRUCTIONS))` renders constitution first |
| R2 | `test_render_blocks_without_order_uses_legacy` | No order → hardcoded sequence | Output identical to current `render_blocks(blocks)` |
| R3 | `test_render_blocks_skips_empty_slots` | Ordered slot with no blocks → no empty tag | No `<topology>` tag when no topology blocks exist |
| R4 | `test_render_topology_extracted_helper` | `_render_topology()` matches the inline code — per-block pattern | Compare with known good output |
| R5 | `test_render_contexts_extracted_helper` | `_render_contexts()` produces same output | Compare with known good output |
| R6 | `test_render_blocks_reminder_via_tagged_blocks` | REMINDER routed through `_render_tagged_blocks` | `<reminder>content</reminder>` present |
| R7 | `test_render_blocks_agent_memory_uses_tagged_renderer` | `kind="agent_memory"` renders as `<agent_memory>` not `<context label="...">` | `<agent_memory>` present, no `<context label="agent_memory">` |

`tests/unit/infrastructure/llm/test_prompt_builder_profiles.py`:

| # | Test | Story | Asserts |
|---|------|-------|---------|
| B1 | `test_builder_no_profile_uses_default` | No profile → `_DEFAULT_PROFILE` | `builder._profile == _DEFAULT_PROFILE` |
| B2 | `test_builder_no_profile_emits_deprecation_warning` | No profile → `DeprecationWarning` | `pytest.warns(DeprecationWarning)` captures warning |
| B3 | `test_builder_explicit_profile_no_warning` | `PromptBuilder(profile=FULL)` → no warning | No `DeprecationWarning` emitted |
| B4 | `test_inactive_slot_skips_add_instructions` | ARBITER → `add_constitution()` is no-op | No `<constitution>` in output |
| B5 | `test_inactive_slot_skips_add_file_before_io` | ARBITER → `add_file()` does not read disk | Mock `path.read_text` never called |
| B6 | `test_inactive_slot_skips_add_mentioned_before_io` | MINIMAL → `add_mentioned_files()` does not read disk | Mock `read_text` never called |
| B7 | `test_active_slot_allows_add` | FULL → `add_constitution()` works | `<constitution>` in output |
| B8 | `test_clone_preserves_profile` | `clone()` copies the profile | `cloned._profile is original._profile` |
| B9 | `test_add_context_with_slot_sets_kind` | `add_context("x", "mem", slot=AGENT_MEMORY)` → block.kind == "agent_memory" | Block kind matches slot value |
| B10 | `test_add_context_default_slot_is_context` | `add_context("x", "label")` → block.kind == "context" | Backward compatible |
| B11 | `test_profile_controls_render_order` | ARBITER → instructions before context, nothing else | Output matches expected order |
| B12 | `test_full_profile_backward_compatible_output` | `PromptBuilder(profile=FULL)` output equals `PromptBuilder()` for same blocks | String equality |
| B13 | `test_is_slot_active_returns_correct` | `_is_slot_active(CONSTITUTION)` on ARBITER → False | Direct method check |

`tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py` — reuses the `mock_db` and
`run_context` fixtures from `conftest.py` in `tests/unit/core/flow/handlers/` (RT-15):

| # | Test | Story | Asserts |
|---|------|-------|---------|
| H1 | `test_build_base_prompt_with_profile_full` | `profile=FULL` → constitution, standards, memory | All blocks present |
| H2 | `test_build_base_prompt_with_profile_interactive` | `profile=INTERACTIVE` → no constitution/standards, has memory | No `<constitution>`, has memory |
| H3 | `test_build_base_prompt_with_profile_arbiter` | `profile=ARBITER` → only instructions + context | No constitution, standards, metadata |
| H4 | `test_build_base_prompt_with_profile_minimal` | `profile=MINIMAL` → only instructions + metadata + topology | No constitution, standards, memory |
| H5 | `test_build_base_prompt_deprecated_include_rules` | `include_rules=False` without profile → works, `DeprecationWarning` | `pytest.warns(DeprecationWarning)`, backward compatible |
| H6 | `test_build_base_prompt_profile_overrides_include_rules` | `profile` + `include_rules=False` → profile wins, `DeprecationWarning` | Profile behavior observed, warning captured |
| H7 | `test_build_base_prompt_memory_skipped_when_slot_inactive` | `profile=MINIMAL` → no memory DB call | Mock DB `async_session_scope` not called |
| H8 | `test_build_base_prompt_memory_hydrated_when_slot_active` | `profile=FULL` + DB → memory block has correct kind | `kind == "agent_memory"` not `"context"` |
| H9 | `test_build_base_prompt_memory_slot_active_but_db_none` | `profile=FULL`, `context.db=None` → no memory block, no error | No `agent_memory` tag, no exception |

Integration (extend `test_prompt_builder_profiles.py`), NFR-3:

| # | Test | File | Story |
|---|------|------|-------|
| I1 | `test_profile_truncation_minimal_tight_budget` | `test_prompt_builder_profiles.py` | MINIMAL under tight budget → only 3 slots compete for space |
| I2 | `test_profile_truncation_full_priority_dropping` | `test_prompt_builder_profiles.py` | FULL under tight budget → low-priority slots dropped first |

H5 and H6 were deleted in SF-03 with `include_rules`.

Verification:

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

Also: `tach check` clean, zero regressions, and the deprecation warning appears for `PromptBuilder()`
without `profile`.

## As built

**Since moved** (noted 2026-09-25): `prompt_builder.py` and `_prompt_render.py` are now
backward-compatibility facades over `infrastructure/llm/prompt/builder.py` and `prompt/render.py`
(`0cd1ed2f`); `_build_base_prompt` lives in `core/flow/handlers/prompting.py` (`0f5f16b9`). Line refs
above are as of the plan's date.
