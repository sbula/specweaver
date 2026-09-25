# C-INTL-05 SF-03 — Caller Migration & Unification

**Status**: APPROVED. Shipped in `0be66689` (2026-05-16). · **FRs owned**: FR-7, FR-8 · **Depends
on**: SF-02 · Design: [C-INTL-05_design.md](C-INTL-05_design.md) §Sub-features → SF-03

## Goal

Every callsite passes an explicit `RenderProfile` constant. The last two maintenance islands go:
`ArbitrateVerdictHandler` (ad-hoc `PromptBuilder()`) and `DecomposeFeatureHandler` /
`FeatureDecomposer` (ad-hoc `PromptBuilder()` bypassing `_build_base_prompt()`).

- **FR-7**: arbiter uses `_build_base_prompt(profile=ARBITER)`.
- **FR-8**: `DecomposeFeatureHandler` pre-builds via `_build_base_prompt(profile=MINIMAL)` and
  injects into `FeatureDecomposer.decompose(base_prompt=...)`.
- Secondary (design callers table): draft `include_rules=False` → `profile=INTERACTIVE`; explicit
  `profile=FULL` on all 3 generation calls, both review calls, and the plan call.
- Cleanup (HITL-approved, see Decisions): remove `include_rules` from `_build_base_prompt()`; remove
  `project_metadata` from `FeatureDecomposer.decompose()` and make `base_prompt` required.

## Where it plugs in

State after SF-02:

| Callsite | File:Line | Current Pattern | Target Profile | Change Type |
|----------|-----------|-----------------|----------------|-------------|
| `DraftSpecHandler._execute_drafting` | `draft.py:80-84` | `_build_base_prompt(include_rules=False)` | `profile=INTERACTIVE` | Replace deprecated param |
| `GenerateCodeHandler.execute` | `generation.py:150-154` | `_build_base_prompt(context, CODE_GEN_INSTRUCTIONS, skeleton_files=s_files)` | `profile=FULL` | Add explicit profile |
| `GenerateTestsHandler.execute` | `generation.py:252-256` | `_build_base_prompt(context, TEST_GEN_INSTRUCTIONS, skeleton_files=s_files)` | `profile=FULL` | Add explicit profile |
| `PlanSpecHandler.execute` | `generation.py:445-449` | `_build_base_prompt(context, PLAN_GENERATION_INSTRUCTIONS, skeleton_files=None)` | `profile=FULL` | Add explicit profile |
| `ReviewSpecHandler.execute` | `review.py:162-166` | `_build_base_prompt(context, SPEC_REVIEW_INSTRUCTIONS, skeleton_files=s_files)` | `profile=FULL` | Add explicit profile |
| `ReviewCodeHandler.execute` | `review.py:273-277` | `_build_base_prompt(context, CODE_REVIEW_INSTRUCTIONS, skeleton_files=s_files)` | `profile=FULL` | Add explicit profile |
| `ArbitrateVerdictHandler.execute` | `arbiter.py:137-144` | Ad-hoc `PromptBuilder()` | `_build_base_prompt(profile=ARBITER)` | **FR-7**: Full rewrite |
| `FeatureDecomposer.decompose` | `decomposer.py:90-91` | Ad-hoc `PromptBuilder()` | Required `base_prompt` param | **FR-8**: DI injection |
| `DecomposeFeatureHandler.execute` | `decompose.py:32-46` | Constructs `FeatureDecomposer` directly | Pre-build `PromptBuilder` via `_build_base_prompt(profile=MINIMAL)` | **FR-8**: Handler wiring |

The design surveyed the same calls with the surrounding adds included: `handlers/draft.py:80-84`,
`handlers/generation.py:150-158`, `handlers/generation.py:252-260`, `handlers/generation.py:445-455`,
`handlers/review.py:162-168`, `handlers/review.py:273-280`, `handlers/arbiter.py:137-144`,
`workflows/planning/decomposer.py:90-91`.

| Module | Context.yaml | Relevant Constraint |
|--------|-------------|---------------------|
| `core/flow/handlers/` | `core/flow/context.yaml` | `archetype: orchestrator`, `consumes: specweaver/llm, specweaver/planning` — may import `_profiles`, `_build_base_prompt`, `PromptBuilder`, and call `FeatureDecomposer` |
| `workflows/planning/` | `workflows/planning/context.yaml` | `archetype: orchestrator`, `consumes: specweaver/llm` — **does NOT consume `specweaver/flow`**. Cannot call `_build_base_prompt()`; receives `PromptBuilder` via DI |
| `infrastructure/llm/` | `infrastructure/llm/context.yaml` | `archetype: adapter`, exposes `PromptSlot`, `RenderProfile`, `PromptBuilder` |

## Decisions (HITL-approved deviations from FR-9)

FR-9 says "zero breaking changes for callers that don't opt into profiles". Two deliberate breaks,
approved by HITL:

1. **`_build_base_prompt()`**: `include_rules: bool` removed entirely. All internal callers use
   `profile=`. The function is internal to `core/flow/handlers/` — NOT a public API in `context.yaml`.
2. **`FeatureDecomposer.decompose()`**: `project_metadata` removed; `base_prompt` required. The
   handler always provides it via `_build_base_prompt(profile=MINIMAL)`.

Why: zero active users, no external callers; both remove dead paths and leave the profile system as
the only path. **`PromptBuilder()` compatibility is NOT affected** — without `profile` it still uses
`_DEFAULT_PROFILE` with all slots active.

## Changes

### 1. `_build_base_prompt()` cleanup · [base.py](../../../../../src/specweaver/core/flow/handlers/base.py)

Remove `include_rules` and its deprecation logic.

```python
# Before (lines 175-221):
async def _build_base_prompt(
    context: RunContext,
    instructions: str,
    *,
    profile: RenderProfile | None = None,
    include_rules: bool = True,
    skeleton_files: dict[str, str] | None = None,
) -> PromptBuilder:
    import warnings
    from specweaver.core.flow.handlers._profiles import FULL, INTERACTIVE
    ...
    if profile is not None and not include_rules:
        warnings.warn(...)
    elif profile is None:
        if include_rules:
            profile = FULL
        else:
            warnings.warn(...)
            profile = INTERACTIVE

# After:
async def _build_base_prompt(
    context: RunContext,
    instructions: str,
    *,
    profile: RenderProfile | None = None,
    skeleton_files: dict[str, str] | None = None,
) -> PromptBuilder:
    from specweaver.core.flow.handlers._profiles import FULL

    if profile is None:
        profile = FULL
    ...
```

`import warnings` and the `INTERACTIVE` import go too — callers pass `INTERACTIVE` themselves.

### 2. Mechanical profile migrations

[draft.py](../../../../../src/specweaver/core/flow/handlers/draft.py): `include_rules=False` →
`profile=INTERACTIVE`.

```python
# Before (line 80-84):
base_prompt = await _build_base_prompt(
    context=context,
    instructions="",
    include_rules=False,
)

# After:
from specweaver.core.flow.handlers._profiles import INTERACTIVE

base_prompt = await _build_base_prompt(
    context=context,
    instructions="",
    profile=INTERACTIVE,
)
```

[generation.py](../../../../../src/specweaver/core/flow/handlers/generation.py): `profile=FULL` on all
three calls (lines 150, 252, 445).

```python
# Add at top of each method's import block:
from specweaver.core.flow.handlers._profiles import FULL

# Each call becomes:
base_prompt = await _build_base_prompt(
    context,
    CODE_GEN_INSTRUCTIONS,  # or TEST_GEN_INSTRUCTIONS, PLAN_GENERATION_INSTRUCTIONS
    profile=FULL,
    skeleton_files=s_files,  # or skeleton_files=None for plan
)
```

[review.py](../../../../../src/specweaver/core/flow/handlers/review.py): `profile=FULL` on both calls
(lines 162, 273).

```python
from specweaver.core.flow.handlers._profiles import FULL

base_prompt = await _build_base_prompt(
    context,
    SPEC_REVIEW_INSTRUCTIONS,  # or CODE_REVIEW_INSTRUCTIONS
    profile=FULL,
    skeleton_files=s_files,
)
```

### 3. Arbiter unification (FR-7) · [arbiter.py](../../../../../src/specweaver/core/flow/handlers/arbiter.py)

Replace the ad-hoc `PromptBuilder()` (lines 137-143) with `_build_base_prompt(profile=ARBITER)`. The
arbiter still calls `context.llm.generate(prompt)` with a **raw string**, not `list[Message]` — only
assembly changes.

```python
# Before (lines 137-144):
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

builder = PromptBuilder()
builder.add_instructions(ARBITRATE_INSTRUCTIONS)
builder.add_context(spec_content, label="Spec Definition")
builder.add_context(filtered_trace, label="Failures")

prompt = builder.build()

# After:
from specweaver.core.flow.handlers.base import _build_base_prompt
from specweaver.core.flow.handlers._profiles import ARBITER

builder = await _build_base_prompt(
    context,
    ARBITRATE_INSTRUCTIONS,
    profile=ARBITER,
)
builder.add_context(spec_content, label="Spec Definition")
builder.add_context(filtered_trace, label="Failures")

prompt = builder.build()
```

Net effect — **identical functional output**:

- ARBITER activates only `{INSTRUCTIONS, CONTEXT}`.
- `add_project_metadata()`, `add_constitution()`, `add_standards()` in `_build_base_prompt()` are
  silently skipped by the SF-02 slot gate.
- Memory hydration short-circuits at `if PromptSlot.AGENT_MEMORY in profile.active_slots` — zero I/O.
- spec_content and filtered_trace are CONTEXT blocks, which ARBITER includes.

### 4. Decomposer IoC injection (FR-8)

[decomposer.py](../../../../../src/specweaver/workflows/planning/decomposer.py): drop
`project_metadata`, require `base_prompt`, clone it instead of building a bare `PromptBuilder()`. The
cloned builder already carries the metadata from `_build_base_prompt()`.

```python
# Before (lines 64-97):
async def decompose(
    self,
    feature_name: str,
    spec_content: str,
    *,
    topology_contexts: list[TopologyContext] | None = None,
    project_metadata: ProjectMetadata | None = None,
) -> DecompositionPlan:
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

    instructions = _DECOMPOSE_INSTRUCTION_TEMPLATE.format(
        feature_name=feature_name,
        spec_content=spec_content,
    )

    builder = (
        PromptBuilder().add_instructions(instructions).add_project_metadata(project_metadata)
    )

    if topology_contexts:
        builder.add_topology(topology_contexts)

# After:
async def decompose(
    self,
    feature_name: str,
    spec_content: str,
    *,
    topology_contexts: list[TopologyContext] | None = None,
    base_prompt: PromptBuilder,
) -> DecompositionPlan:
    instructions = _DECOMPOSE_INSTRUCTION_TEMPLATE.format(
        feature_name=feature_name,
        spec_content=spec_content,
    )

    builder = base_prompt.clone()
    builder.add_instructions(instructions)

    if topology_contexts:
        builder.add_topology(topology_contexts)
```

Imports (RT-4): add `from specweaver.infrastructure.llm.prompt_builder import PromptBuilder` to the
`TYPE_CHECKING` block (lines 19-22) so mypy resolves the annotation; remove the inline import from the
method body. On line 16, remove only `ProjectMetadata` from the `specweaver.infrastructure.llm.models`
import — `GenerationConfig` and `Message` stay.

[decompose.py](../../../../../src/specweaver/core/flow/handlers/decompose.py): pre-build via
`_build_base_prompt(profile=MINIMAL)`, pass `base_prompt=`, drop `project_metadata=`.

```python
# Before (lines 27-46):
try:
    feature_name = step.params.get("feature_name", "unknown_feature")

    decomposer = FeatureDecomposer(
        llm=context.llm, context_provider=context.context_provider
    )

    spec_content = ""
    if context.spec_path.exists():
        spec_content = context.spec_path.read_text(encoding="utf-8")

    plan = await decomposer.decompose(
        feature_name=feature_name,
        spec_content=spec_content,
        topology_contexts=[context.topology] if context.topology else None,
        project_metadata=context.project_metadata,
    )

# After:
try:
    from specweaver.core.flow.handlers.base import _build_base_prompt
    from specweaver.core.flow.handlers._profiles import MINIMAL

    feature_name = step.params.get("feature_name", "unknown_feature")

    base_prompt = await _build_base_prompt(
        context,
        "",  # Instructions are set by the decomposer itself
        profile=MINIMAL,
    )

    decomposer = FeatureDecomposer(
        llm=context.llm, context_provider=context.context_provider
    )

    spec_content = ""
    if context.spec_path.exists():
        spec_content = context.spec_path.read_text(encoding="utf-8")

    plan = await decomposer.decompose(
        feature_name=feature_name,
        spec_content=spec_content,
        topology_contexts=[context.topology] if context.topology else None,
        base_prompt=base_prompt,
    )
```

### 5. Drafter & FeatureDrafter IoC (RT-23)

`src/specweaver/workflows/drafting/drafter.py` and `src/specweaver/workflows/drafting/feature_drafter.py`:
`base_prompt` becomes required; the `PromptBuilder()` fallback goes.

```python
# Before (__init__):
def __init__(
    self,
    llm: LLMAdapter,
    context_provider: ContextProvider,
    config: GenerationConfig | None = None,
    base_prompt: PromptBuilder | None = None,
) -> None:
    ...
    self._base_prompt = base_prompt

# Before (_generate_section):
builder = self._base_prompt.clone() if self._base_prompt else PromptBuilder()

# After (__init__):
def __init__(
    self,
    llm: LLMAdapter,
    context_provider: ContextProvider,
    base_prompt: PromptBuilder,
    *,
    config: GenerationConfig | None = None,
) -> None:
    ...
    self._base_prompt = base_prompt

# After (_generate_section):
builder = self._base_prompt.clone()
```

~40 unit tests in `tests/unit/workflows/drafting/` then fail with
`TypeError: missing 1 required positional argument: 'base_prompt'`; a script injects
`base_prompt=PromptBuilder(profile=INTERACTIVE)` into them during the `dev.md` phase.

One commit boundary: `_build_base_prompt()` cleanup, mechanical profiles (draft, generation, review,
plan), arbiter (FR-7), decomposer (FR-8), drafters (RT-23), all new tests, existing test updates.

## Tests

[NEW] `tests/unit/core/flow/handlers/test_caller_migration.py`:

| Test ID | Test | Verifies |
|---------|------|----------|
| M1 | `test_draft_handler_uses_interactive_profile` | draft.py calls `_build_base_prompt(profile=INTERACTIVE)` |
| M2 | `test_generate_code_uses_full_profile` | generation.py GenerateCodeHandler passes `profile=FULL` |
| M3 | `test_generate_tests_uses_full_profile` | generation.py GenerateTestsHandler passes `profile=FULL` |
| M4 | `test_plan_spec_uses_full_profile` | generation.py PlanSpecHandler passes `profile=FULL` |
| M5 | `test_review_spec_uses_full_profile` | review.py ReviewSpecHandler passes `profile=FULL` |
| M6 | `test_review_code_uses_full_profile` | review.py ReviewCodeHandler passes `profile=FULL` |
| A1 | `test_arbiter_uses_build_base_prompt_with_arbiter_profile` | arbiter.py uses `_build_base_prompt(profile=ARBITER)` |
| A2 | `test_arbiter_context_blocks_rendered_under_arbiter_profile` | spec + trace context blocks appear under ARBITER |
| A3 | `test_arbiter_no_constitution_or_metadata_in_prompt` | ARBITER excludes constitution, standards, metadata |
| D1 | `test_decompose_handler_injects_base_prompt_with_minimal_profile` | decompose.py calls `_build_base_prompt(profile=MINIMAL)` and passes the result on |
| D2 | `test_decomposer_clones_injected_base_prompt` | decomposer.py clones the provided base_prompt |
| D3 | `test_decomposer_requires_base_prompt` | decomposer.py raises TypeError if `base_prompt` is missing |

[NEW] `tests/integration/core/flow/handlers/test_caller_migration_integration.py`:

| Test ID | Test | Verifies |
|---------|------|----------|
| I1 | `test_arbiter_full_execution_with_profile` | Full ArbitrateVerdictHandler.execute() with mocked LLM: profile-driven assembly + verdict parsing |
| I2 | `test_decompose_handler_full_execution_with_profile` | Full DecomposeFeatureHandler.execute(): decomposer receives a profile-gated PromptBuilder |

Existing tests:

- `tests/unit/workflows/planning/test_decomposer.py` — add `base_prompt=PromptBuilder(profile=MINIMAL)`
  to all `decompose()` calls in `test_decompose_returns_plan`, `test_decompose_llm_exception`,
  `test_decompose_pydantic_validation_error`. Never bare `PromptBuilder()` — it raises a
  `DeprecationWarning` (prompt_builder.py:91-96) (RT-15).

```python
from specweaver.core.flow.handlers._profiles import MINIMAL
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

# In each test:
base_prompt=PromptBuilder(profile=MINIMAL)
```

- `tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py` — delete H5
  `test_build_base_prompt_deprecated_include_rules` and H6
  `test_build_base_prompt_profile_overrides_include_rules` (both test the removed param).
- `tests/unit/core/flow/handlers/test_build_base_prompt.py` (RT-19) —
  `test_build_base_prompt_include_rules_false` (line 87) calls
  `_build_base_prompt(..., include_rules=False)`; migrate to
  `profile=INTERACTIVE`, rename to `test_build_base_prompt_interactive_profile`, update the docstring
  at line 15. Assertions unchanged (INTERACTIVE excludes constitution/standards, includes memory).

```python
# Before (line 94):
builder = await _build_base_prompt(run_context, "Drafting tier 2", include_rules=False)

# After:
from specweaver.core.flow.handlers._profiles import INTERACTIVE
builder = await _build_base_prompt(run_context, "Drafting tier 2", profile=INTERACTIVE)
```

Verification:

1. `pytest tests/unit/core/flow/handlers/test_caller_migration.py -v`
2. `pytest tests/integration/core/flow/handlers/test_caller_migration_integration.py -v`
3. `pytest tests/unit/core/flow/handlers/ -v` (all existing handler tests)
4. `pytest tests/unit/workflows/planning/test_decomposer.py -v`
5. `pytest` (full suite, 4,800+ tests)
6. `tach check` — 0 violations
7. `python -m mypy src/specweaver/core/flow/handlers/ src/specweaver/workflows/planning/decomposer.py`
8. `python -m ruff check src/specweaver/core/flow/handlers/ src/specweaver/workflows/planning/decomposer.py`
9. `python -m ruff format --check src/specweaver/core/flow/handlers/ src/specweaver/workflows/planning/decomposer.py`
10. `grep -r "include_rules" src/` — zero matches
11. `grep -r "include_rules" tests/` — zero matches (RT-19)

Docs: `adding_prompt_slots.md` examples stay accurate (checked); `architecture_reference.md` and user
guides unchanged (internal refactoring); `master_story_roadmap.md` and `capability_matrix.md` updated
only once all 3 SFs were complete.

## As built

**Since moved** (noted 2026-09-25): `_build_base_prompt` → `core/flow/handlers/prompting.py`
(`0f5f16b9`); the drafters' `base_prompt` constructor → `workflows/drafting/_base.py`. Line refs above
are as of the plan's date.
