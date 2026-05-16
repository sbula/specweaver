# Implementation Plan: Configurable Prompt Render Profiles [SF-03: Caller Migration & Unification]
- **Feature ID**: C-INTL-05
- **Sub-Feature**: SF-03 — Caller Migration & Unification
- **Design Document**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_sf03_implementation_plan.md
- **Status**: APPROVED

## Overview

SF-03 completes the C-INTL-05 feature by migrating **all** remaining callsites to use explicit `RenderProfile` constants and eliminating the last two "maintenance islands" — `ArbitrateVerdictHandler` (ad-hoc `PromptBuilder()`) and `DecomposeFeatureHandler` / `FeatureDecomposer` (ad-hoc `PromptBuilder()` bypassing `_build_base_prompt()`).

**Primary scope** (from design doc §SF-03):
- **FR-7**: Arbiter Handler Unification — replace ad-hoc `PromptBuilder()` construction with `_build_base_prompt(profile=ARBITER)`.
- **FR-8**: Decomposer IoC Injection — `DecomposeFeatureHandler` pre-builds a `PromptBuilder` via `_build_base_prompt(profile=MINIMAL)` and injects it into `FeatureDecomposer.decompose(base_prompt=...)`.

**Secondary scope** (from design doc callers table):
- **Draft handler**: Replace `include_rules=False` with `profile=INTERACTIVE`.
- **Generation handlers**: Add explicit `profile=FULL` to all 3 `_build_base_prompt()` calls.
- **Review handlers**: Add explicit `profile=FULL` to both `_build_base_prompt()` calls.
- **Plan handler**: Add explicit `profile=FULL` to the `_build_base_prompt()` call.

**Cleanup scope** (approved HITL deviations):
- Remove deprecated `include_rules` parameter from `_build_base_prompt()`.
- Remove `project_metadata` parameter from `FeatureDecomposer.decompose()`, make `base_prompt` required.

## HITL-Approved Deviations

> [!WARNING]
> **Deviation from FR-9 (Backward Compatibility)**: FR-9 mandates "zero breaking changes for callers that don't opt into profiles". This SF introduces two deliberate breaking changes approved by HITL:
>
> 1. **`_build_base_prompt()` signature**: The `include_rules: bool` parameter is removed entirely. All internal callers have been migrated to `profile=`. This function is internal to `core/flow/handlers/` — it is NOT a public API exposed via `context.yaml`.
>
> 2. **`FeatureDecomposer.decompose()` signature**: The `project_metadata` parameter is removed. The `base_prompt` parameter becomes required (non-optional). The handler always provides it via `_build_base_prompt(profile=MINIMAL)`.
>
> **Justification**: Zero active users. No external callers. Both changes eliminate dead code paths and enforce the profile-driven architecture as the only path.
>
> **FR-9's `PromptBuilder()` backward compatibility is NOT affected.** The `PromptBuilder()` constructor without a `profile` argument continues to use `_DEFAULT_PROFILE` with all slots active. This remains unchanged.

## Research Notes

### Codebase State (Post SF-02)

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

### Boundary Constraints Verified

| Module | Context.yaml | Relevant Constraint |
|--------|-------------|---------------------|
| `core/flow/handlers/` | `core/flow/context.yaml` | `archetype: orchestrator`, `consumes: specweaver/llm, specweaver/planning` — legal to import `_profiles`, `_build_base_prompt`, `PromptBuilder`, and to call `FeatureDecomposer` |
| `workflows/planning/` | `workflows/planning/context.yaml` | `archetype: orchestrator`, `consumes: specweaver/llm` — **does NOT consume `specweaver/flow`**. Cannot call `_build_base_prompt()`. Must receive `PromptBuilder` via DI |
| `infrastructure/llm/` | `infrastructure/llm/context.yaml` | `archetype: adapter`, exposes `PromptSlot`, `RenderProfile`, `PromptBuilder` |

## Proposed Changes

### Component 1: `_build_base_prompt()` Cleanup

#### [MODIFY] [base.py](../../../../../src/specweaver/core/flow/handlers/base.py)

**Change**: Remove the `include_rules: bool` parameter and the associated deprecation logic.

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

> [!CAUTION]
> The `import warnings` and `from ... import INTERACTIVE` lines at the top of the function body can be removed since the deprecation path is deleted. The `INTERACTIVE` import is no longer needed inside `_build_base_prompt` — callers pass it explicitly.

---

### Component 2: Simple Profile Migrations (Mechanical)

These are low-risk, mechanical substitutions that add explicit `profile=` kwargs to existing `_build_base_prompt()` calls.

#### [MODIFY] [draft.py](../../../../../src/specweaver/core/flow/handlers/draft.py)

**Change**: Replace `include_rules=False` with `profile=INTERACTIVE`.

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

#### [MODIFY] [generation.py](../../../../../src/specweaver/core/flow/handlers/generation.py)

**Change**: Add `profile=FULL` to all three `_build_base_prompt()` calls (lines 150, 252, 445).

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

#### [MODIFY] [review.py](../../../../../src/specweaver/core/flow/handlers/review.py)

**Change**: Add `profile=FULL` to both `_build_base_prompt()` calls (lines 162, 273).

```python
from specweaver.core.flow.handlers._profiles import FULL

base_prompt = await _build_base_prompt(
    context,
    SPEC_REVIEW_INSTRUCTIONS,  # or CODE_REVIEW_INSTRUCTIONS
    profile=FULL,
    skeleton_files=s_files,
)
```

---

### Component 3: Arbiter Handler Unification (FR-7)

#### [MODIFY] [arbiter.py](../../../../../src/specweaver/core/flow/handlers/arbiter.py)

**Change**: Replace the ad-hoc `PromptBuilder()` construction (lines 137-143) with a call to `_build_base_prompt(profile=ARBITER)`.

> [!IMPORTANT]
> The Arbiter uses `context.llm.generate(prompt)` with a **raw string**, not `list[Message]`. This call pattern is unchanged — only the prompt assembly is refactored.

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

**Behavioral Impact**:
- ARBITER profile activates only `{INSTRUCTIONS, CONTEXT}` slots.
- `_build_base_prompt()` calls `add_project_metadata()`, `add_constitution()`, `add_standards()` — all silently skipped by slot gating (SF-02) since those slots are NOT in ARBITER's `active_slots`.
- Memory hydration is short-circuited at the `if PromptSlot.AGENT_MEMORY in profile.active_slots` check — zero I/O cost.
- spec_content and filtered_trace are added as CONTEXT blocks — CONTEXT IS in the ARBITER profile. They render correctly.
- **Net effect: identical functional output** to the current ad-hoc construction.

---

### Component 4: Decomposer IoC Injection (FR-8)

#### [MODIFY] [decomposer.py](../../../../../src/specweaver/workflows/planning/decomposer.py)

**Change**: Remove `project_metadata` parameter. Make `base_prompt` a required `PromptBuilder` parameter. Clone it instead of creating a bare `PromptBuilder()`.

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

> [!CAUTION]
> **RT-4 Fix**: The `TYPE_CHECKING` block (lines 19-22) MUST add `from specweaver.infrastructure.llm.prompt_builder import PromptBuilder` so mypy resolves the type annotation. The inline `from specweaver.infrastructure.llm.prompt_builder import PromptBuilder` that was inside the method body is removed. Also remove `ProjectMetadata` from the runtime import on line 16.

> [!NOTE]
> - `project_metadata` is removed — the cloned builder already contains it from `_build_base_prompt()`.
> - `from specweaver.infrastructure.llm.prompt_builder import PromptBuilder` inline import is removed — no longer needed since we don't construct a bare `PromptBuilder()`.
> - The `TYPE_CHECKING` block must add `from specweaver.infrastructure.llm.prompt_builder import PromptBuilder` for the type annotation.
> - The `ProjectMetadata` import in the module-level imports can be cleaned up if no longer used elsewhere in the file. **Check**: the `GenerationConfig` and `Message` imports on line 16 use models from `specweaver.infrastructure.llm.models` — `ProjectMetadata` is imported there too. Remove only `ProjectMetadata` from that import line since it's no longer used in the method signature.

#### [MODIFY] [decompose.py](../../../../../src/specweaver/core/flow/handlers/decompose.py)

**Change**: Pre-build a `PromptBuilder` via `_build_base_prompt(profile=MINIMAL)` and inject it into `FeatureDecomposer.decompose(base_prompt=...)`. Remove `project_metadata=` from the `decompose()` call.

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

---

### Component 5: Drafter & FeatureDrafter IoC Unification (RT-23)

#### [MODIFY] src/specweaver/workflows/drafting/drafter.py
#### [MODIFY] src/specweaver/workflows/drafting/feature_drafter.py

**Change**: Make `base_prompt` strictly required and remove the `PromptBuilder()` instantiation fallback. This completes the DI architectural unification.

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

> [!IMPORTANT]  
> Changing `base_prompt` to be required means ~40 existing unit tests in `tests/unit/workflows/drafting/` will fail with `TypeError: missing 1 required positional argument: 'base_prompt'`. We will update all affected tests by injecting `base_prompt=PromptBuilder(profile=INTERACTIVE)` during the `dev.md` execution phase using an automated script.

---

### Component 6: Test Updates

#### [NEW] tests/unit/core/flow/handlers/test_caller_migration.py

**New unit tests for the profile migrations, FR-7, and FR-8.**

| Test ID | Test | Verifies |
|---------|------|----------|
| M1 | `test_draft_handler_uses_interactive_profile` | draft.py calls `_build_base_prompt(profile=INTERACTIVE)` |
| M2 | `test_generate_code_uses_full_profile` | generation.py GenerateCodeHandler passes `profile=FULL` |
| M3 | `test_generate_tests_uses_full_profile` | generation.py GenerateTestsHandler passes `profile=FULL` |
| M4 | `test_plan_spec_uses_full_profile` | generation.py PlanSpecHandler passes `profile=FULL` |
| M5 | `test_review_spec_uses_full_profile` | review.py ReviewSpecHandler passes `profile=FULL` |
| M6 | `test_review_code_uses_full_profile` | review.py ReviewCodeHandler passes `profile=FULL` |
| A1 | `test_arbiter_uses_build_base_prompt_with_arbiter_profile` | arbiter.py uses `_build_base_prompt(profile=ARBITER)` |
| A2 | `test_arbiter_context_blocks_rendered_under_arbiter_profile` | spec + trace context blocks appear in output under ARBITER profile |
| A3 | `test_arbiter_no_constitution_or_metadata_in_prompt` | ARBITER profile excludes constitution, standards, and metadata |
| D1 | `test_decompose_handler_injects_base_prompt_with_minimal_profile` | decompose.py calls `_build_base_prompt(profile=MINIMAL)` and passes result to decomposer |
| D2 | `test_decomposer_clones_injected_base_prompt` | decomposer.py clones the provided base_prompt |
| D3 | `test_decomposer_requires_base_prompt` | decomposer.py raises TypeError if `base_prompt` is missing |

#### [NEW] tests/integration/core/flow/handlers/test_caller_migration_integration.py

| Test ID | Test | Verifies |
|---------|------|----------|
| I1 | `test_arbiter_full_execution_with_profile` | Full ArbitrateVerdictHandler.execute() path with mocked LLM, verifying profile-driven assembly + verdict parsing |
| I2 | `test_decompose_handler_full_execution_with_profile` | Full DecomposeFeatureHandler.execute() path, verifying decomposer receives profile-gated PromptBuilder |

#### [MODIFY] tests/unit/workflows/planning/test_decomposer.py

**Update 3 existing tests** — add `base_prompt=PromptBuilder(profile=MINIMAL)` to all `decompose()` calls:

> [!CAUTION]
> **RT-15 Fix**: Do NOT use bare `PromptBuilder()` — it triggers a `DeprecationWarning` (prompt_builder.py:91-96). Always pass an explicit profile to match the production path.

```python
from specweaver.core.flow.handlers._profiles import MINIMAL
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

# In each test:
base_prompt=PromptBuilder(profile=MINIMAL)
```

- `test_decompose_returns_plan` — add `base_prompt=PromptBuilder(profile=MINIMAL)`
- `test_decompose_llm_exception` — add `base_prompt=PromptBuilder(profile=MINIMAL)`
- `test_decompose_pydantic_validation_error` — add `base_prompt=PromptBuilder(profile=MINIMAL)`

#### [MODIFY] tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py

**Delete 2 deprecated tests** (H5 and H6):
- `test_build_base_prompt_deprecated_include_rules` — tests removed `include_rules` param
- `test_build_base_prompt_profile_overrides_include_rules` — tests removed `include_rules` param

#### [MODIFY] tests/unit/core/flow/handlers/test_build_base_prompt.py

> [!CAUTION]
> **RT-19 Fix**: This file contains `test_build_base_prompt_include_rules_false` (line 87) which calls `_build_base_prompt(..., include_rules=False)`. Since `include_rules` is removed, this test MUST be migrated.

**Migrate 1 test** — replace `include_rules=False` with `profile=INTERACTIVE`:

```python
# Before (line 94):
builder = await _build_base_prompt(run_context, "Drafting tier 2", include_rules=False)

# After:
from specweaver.core.flow.handlers._profiles import INTERACTIVE
builder = await _build_base_prompt(run_context, "Drafting tier 2", profile=INTERACTIVE)
```

- Rename test: `test_build_base_prompt_include_rules_false` → `test_build_base_prompt_interactive_profile`
- Update the docstring at line 15 to match the new test name
- Assertions remain identical (INTERACTIVE excludes constitution/standards, includes memory)

---

## Commit Boundary

**Single Commit Boundary** — all changes ship together:
1. `_build_base_prompt()` cleanup (remove `include_rules`)
2. Mechanical profile additions to draft, generation, review, plan handlers
3. Arbiter handler unification (FR-7)
4. Decomposer IoC injection (FR-8)
5. Drafter & FeatureDrafter IoC injection (RT-23)
6. All new tests (unit + integration)
7. Existing test updates (decomposer, drafter, + profile tests)

## Verification Plan

### Automated Tests
1. `pytest tests/unit/core/flow/handlers/test_caller_migration.py -v`
2. `pytest tests/integration/core/flow/handlers/test_caller_migration_integration.py -v`
3. `pytest tests/unit/core/flow/handlers/ -v` (all existing handler tests)
4. `pytest tests/unit/workflows/planning/test_decomposer.py -v` (updated decomposer tests)
5. `pytest` (full suite, 4,800+ tests)
6. `tach check` — 0 violations
7. `python -m mypy src/specweaver/core/flow/handlers/ src/specweaver/workflows/planning/decomposer.py`
8. `python -m ruff check src/specweaver/core/flow/handlers/ src/specweaver/workflows/planning/decomposer.py`
9. `python -m ruff format --check src/specweaver/core/flow/handlers/ src/specweaver/workflows/planning/decomposer.py`
10. `grep -r "include_rules" src/` — must return zero matches
11. `grep -r "include_rules" tests/` — must return zero matches (RT-19 verified)

### Manual Verification
- Verify `adding_prompt_slots.md` dev guide examples remain accurate

## Documentation Updates

| Document | Update Required |
|----------|----------------|
| `C-INTL-05_design.md` Progress Tracker | Mark `Impl Plan ✅` for SF-03 |
| `C-INTL-05_design.md` Session Handoff | Update to point to `/dev` for SF-03 |
| `adding_prompt_slots.md` | No changes needed |
| `architecture_reference.md` | No changes needed |
| User Guides | No changes — internal refactoring |
| `master_story_roadmap.md` | No changes until all 3 SFs complete |
| `capability_matrix.md` | No changes until all 3 SFs complete |
