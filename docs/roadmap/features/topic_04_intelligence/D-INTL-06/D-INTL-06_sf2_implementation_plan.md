# Implementation Plan: Context Hydration & Handover Engine [SF-2: Prompt Assembly via Inversion of Control]
- **Feature ID**: D-INTL-06
- **Sub-Feature**: SF-2 — Prompt Assembly via Inversion of Control
- **Design Document**: docs/roadmap/features/topic_04_intelligence/D-INTL-06/D-INTL-06_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/D-INTL-06/D-INTL-06_sf2_implementation_plan.md
- **Status**: DRAFT

---

## Scope Summary

SF-2 centralizes prompt assembly via **Inversion of Control** in the Application Layer. A module-level async function `_build_base_prompt()` in `core.flow.handlers.base` builds a base `PromptBuilder` (instructions, project metadata, constitution, standards, memory hydration) and each handler passes it down to its Domain Layer workflow method. Each workflow method adds only its domain-specific blocks on top.

This eliminates a ~150-line DRY violation across the codebase and establishes a single integration point for all future context sources — without introducing a `workflows/commons` module, which would violate DDD bounded context isolation.

### Modified Files

**Application Layer (`core.flow.handlers`):**
- `src/specweaver/core/flow/handlers/base.py` — Add `async _build_base_prompt()` with fail-safe memory hydration
- `src/specweaver/core/flow/handlers/generation.py` — Call `_build_base_prompt()`, pass builder to generator
- `src/specweaver/core/flow/handlers/review.py` — Call `_build_base_prompt()`, pass builder to reviewer
- `src/specweaver/core/flow/handlers/draft.py` — Call `_build_base_prompt(..., include_rules=False)`, pass builder to drafter (2-Tier enforcement)

**Domain Layer (`workflows`):**
- `src/specweaver/workflows/implementation/generator.py` — Replace param list with `base_prompt: PromptBuilder`
- `src/specweaver/workflows/review/reviewer.py` — Replace param list with `base_prompt: PromptBuilder`
- `src/specweaver/workflows/planning/planner.py` — Replace param list with `base_prompt: PromptBuilder`
- `src/specweaver/workflows/drafting/drafter.py` — Replace param list with `base_prompt: PromptBuilder`
- `src/specweaver/workflows/drafting/feature_drafter.py` — Replace param list with `base_prompt: PromptBuilder`

**Boundary Declarations:**
- `src/specweaver/core/flow/context.yaml` — Add `specweaver/workspace/memory` to `consumes`
- `tach.toml` — Add `src.specweaver.workspace.memory` to `core.flow` `depends_on`

### Test Files
- `tests/unit/core/flow/handlers/test_build_base_prompt.py` — NEW (unit tests for `_build_base_prompt`)
- `tests/integration/core/flow/handlers/test_prompt_hydration.py` — NEW (integration with in-memory SQLite)
- Regression updates within each modified workflow module test file

### NOT Modified (Explicitly Excluded)
- `RunContext` (no new fields — `db` and `project_path` already exist)
- `PromptBuilder` (no new methods — uses existing `add_context()`)
- `interfaces/cli/*` (no CLI changes)
- `interfaces/api/*` (no API changes)
- `ArbiterHandler` (uses minimal prompt via raw `Message` — excluded per FR-6)
- `workflows/planning/decomposer.py` (Excluded per HITL Phase 4 — operates at different abstraction level)
- `workflows/scenarios/scenario_generator.py` (Does NOT use `PromptBuilder` — builds raw string prompts directly. No refactoring needed.)
- All workflow `context.yaml` files (no new domain dependencies introduced)

**FRs covered**: FR-6 (Base Prompt Assembly), FR-7 (Handler Assembly Method)
**NFRs covered**: NFR-2 (architectural placement), NFR-5 (backward compat), NFR-6 (observability), NFR-7 (test coverage), NFR-8 (file size), NFR-9 (fail-safe hydration)

---

## Research Notes

### RN-1: Decomposer PromptBuilder Usage — 6th Module Not in Design Scope

**Source**: `workflows/planning/decomposer.py:83-97`

The design doc says "5 workflow modules" use PromptBuilder. In practice, there are **6 files** with PromptBuilder usage:
1. `generator.py` — `generate_code()` + `generate_tests()` (2 call sites)
2. `reviewer.py` — `review_spec()` + `review_code()` (2 call sites)
3. `planner.py` — `generate_plan()` (1 call site)
4. `drafter.py` — `_generate_section()` (1 call site)
5. `feature_drafter.py` — `_generate_section()` (1 call site)
6. `decomposer.py` — `decompose()` (1 call site)

The `decomposer.py` has a **minimal** PromptBuilder usage (no constitution, no standards, no plan, no skeleton_files).

**Resolved**: Excluded (HITL Phase 4 Decision). The decomposer does not generate code, it generates a structural architecture map. Constitution/standards are irrelevant to it.

### RN-2: Prompt Assembly Chain Differences Across Modules

Analyzing the exact assembly chain per module reveals significant variation:

| Module | instructions | project_metadata | file | constitution | standards | plan | topology | env_context | skeleton_files | dictator | validation | mentioned_files |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| generator.generate_code | ✅ | ✅ | ✅ | ✅ | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| generator.generate_tests | ✅ | ✅ | ✅ | ✅ | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| reviewer.review_spec | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| reviewer.review_code | ✅ | ✅ | ✅✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| planner.generate_plan | ✅✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| drafter._generate_section | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| feature_drafter._generate_section | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Impact**: The `_build_base_prompt()` method produces a **base** PromptBuilder (instructions + project_metadata + constitution + standards + memory context). Each handler then adds handler-specific blocks (plan, topology, skeleton_files) before passing the builder to the workflow method. The workflow method adds only domain-specific blocks (file, dictator, validation, etc.).

### RN-3: PromptBuilder `add_context()` Signature (Verified)

**Source**: `infrastructure/llm/prompt_builder.py:178-201`

```python
def add_context(self, text: str, label: str, *, priority: int = 3) -> PromptBuilder:
```

Per design: `_build_base_prompt` calls `builder.add_context(block, "agent_memory", priority=2)`.

### RN-4: RunContext Already Has `db` and `project_path`

**Source**: `core/flow/handlers/base.py:28-71`

- `context.db: Any = None` — Database instance (line 60)
- `context.project_path: Path` — Required field (line 45)

`_build_base_prompt()` accesses these directly from `RunContext`. No parameter threading through workflow methods needed for hydration.

### RN-5: `tach.toml` — `core.flow` Needs `workspace.memory` Dependency

**Source**: `tach.toml:15`

`core.flow` currently has `depends_on = []`. To legally import `MemoryHydrator` from `workspace.memory`, we must add `src.specweaver.workspace.memory` to its `depends_on` list. The `workspace.memory` module already has an `[[interfaces]]` entry exposing `hydrator` (line 243-244).

### RN-6: `standards` Param Not Passed by Generator Handler

**Source**: `core/flow/handlers/generation.py:146-158`

The `GenerateCodeHandler` passes `constitution=context.constitution` but NOT `standards=context.standards` at lines 146-158 (`generate_code()`) and lines 236-250 (`generate_tests()`). This is currently a bug/missing feature — the generator's `generate_code()` signature accepts `standards` but the handler doesn't pass it. The `_generate_plan_artifact()` method (line 352-361) DOES pass both `constitution` and `standards`. The reviewer handler also passes both.

**Impact**: Pre-SF-2 Hotfix. A separate commit will add `standards=context.standards` to both `GenerateCodeHandler._execute()` and `GenerateTestsHandler._execute()`. The SF-2 refactoring will then centralize this fix inside `_build_base_prompt()`.

### RN-11: ScenarioGenerator Does NOT Use PromptBuilder

**Source**: `workflows/scenarios/scenario_generator.py:47-86, 183-227`

`ScenarioGenerator.generate_scenarios()` builds a raw string prompt via `_build_prompt()` (static method) and calls `self._llm.generate(prompt)` directly — it does NOT use `PromptBuilder`. The handler (`core/flow/handlers/scenario.py`) passes `constitution` and `project_metadata` as individual params. This module is completely outside the `_build_base_prompt()` refactoring scope.

**Resolved**: Explicitly excluded. No PromptBuilder usage, no refactoring needed.

### RN-12: Handler Coverage Audit — All 16 Handler Files Verified

**Source**: `core/flow/handlers/` directory listing (16 files)

Full audit of which handlers are in scope:

| Handler File | Uses PromptBuilder? | In Scope? | Notes |
|---|:-:|:-:|---|
| `generation.py` | Via workflow | ✅ | `generate_code`, `generate_tests`, `_generate_plan_artifact` |
| `review.py` | Via workflow | ✅ | `review_spec`, `review_code` |
| `draft.py` | Via workflow | ✅ | `_generate_section` (drafter + feature_drafter) |
| `arbiter.py` | Raw `Message` | ❌ | Excluded (FR-6) |
| `scenario.py` | Via raw string | ❌ | ScenarioGenerator doesn't use PromptBuilder (RN-11) |
| `decompose.py` | Via workflow | ❌ | Excluded (HITL Phase 4) |
| `base.py` | NEW | ✅ | `_build_base_prompt()` added here |
| `context_assembler.py` | No | ❌ | Topology assembly only |
| `contract_renderers.py` | No | ❌ | Contract rendering only |
| `dual_pipeline.py` | No | ❌ | Pipeline orchestration |
| `lint_fix.py` | No | ❌ | Lint fix handler |
| `mcp_assembler.py` | No | ❌ | MCP assembly only |
| `registry.py` | No | ❌ | Handler registry |
| `standards.py` | No | ❌ | Standards handler |
| `drift.py` | No | ❌ | Drift detection |
| `validation.py` | No | ❌ | Validation handler |

### RN-7: `async_session_scope()` Pattern for Hydration

**Source**: `core/flow/handlers/generation.py:163-172`

The existing pattern for database access from handlers:
```python
if context.db:
    async with context.db.async_session_scope() as session:
        # ... use session ...
```

`_build_base_prompt()` uses this same pattern for hydration. The method must be `async` to support `async with`.

### RN-8: Arbiter Exclusion is Correct

**Source**: `core/flow/handlers/arbiter.py`

The `ArbiterHandler` builds prompts using raw `Message` construction, NOT via `PromptBuilder`. It has no overlap with the base prompt assembly. Exclusion is architecturally correct.

### RN-9: `context.yaml` `consumes` — `core.flow` Needs `workspace/memory`

**Source**: `core/flow/context.yaml:18-31`

`core.flow` currently consumes `specweaver/config`, `specweaver/llm`, `specweaver/review`, `specweaver/implementation`, `specweaver/planning`, `specweaver/validation`, and several sandbox modules. It does NOT currently consume `specweaver/workspace/memory`. This must be added.

No workflow `context.yaml` files need updating — workflow modules receive a pre-built `PromptBuilder` and do not import `workspace.memory` themselves.

### RN-10: Inline Import Pattern Is Established

All 5 workflow modules import `PromptBuilder` inside their methods (inline imports). This is acknowledged tech debt (anti-pattern in architecture reference) but is the established codebase pattern for breaking circular imports. `_build_base_prompt()` will use the same inline import pattern for `PromptBuilder` and `MemoryHydrator`.

---

## Proposed Changes

### Commit Boundary 1: Foundation — `_build_base_prompt()`

#### [MODIFY] `core/flow/handlers/base.py`
Add a module-level async function (not a method on any class — `base.py` defines `RunContext` and `StepHandler` protocol, there is no `BaseHandler` class):

```python
async def _build_base_prompt(
    context: RunContext,
    instructions: str,
    *,
    include_rules: bool = True,
    skeleton_files: dict[str, str] | None = None,
) -> "PromptBuilder":
    """Build a PromptBuilder with base context (instructions, metadata, rules, memory).

    Args:
        context: The RunContext for this pipeline step.
        instructions: Module-specific instruction text.
        include_rules: If False, skips constitution and standards (2-Tier Handover for Drafts).
        skeleton_files: Optional skeleton files for PromptBuilder constructor.

    Returns:
        A partially-built PromptBuilder ready for domain-specific additions.

    The memory hydration is fail-safe: any exception during hydration (db=None,
    DB failure, Pydantic error) is caught and logged at WARNING. The returned
    PromptBuilder simply lacks the agent_memory block.
    """
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

    builder = PromptBuilder(skeleton_files=skeleton_files)
    builder.add_instructions(instructions)
    builder.add_project_metadata(context.project_metadata)

    # Tier 1 Rules — gated by include_rules (False for drafting)
    if include_rules:
        if context.constitution:
            builder.add_constitution(context.constitution)
        if context.standards:
            builder.add_standards(context.standards)

    # Memory Hydration — fail-safe
    if context.db is not None and context.project_path is not None:
        try:
            from specweaver.workspace.memory.hydrator import MemoryHydrator

            async with context.db.async_session_scope() as session:
                hydrator = MemoryHydrator(session, context.project_path.name)
                result = await hydrator.hydrate()
                if result.task_count > 0:
                    block = result.format_prompt_block()
                    builder.add_context(block, "agent_memory", priority=2)
                    logger.info(
                        "Hydration: %d tasks, %d tokens",
                        result.task_count,
                        result.token_estimate,
                    )
        except Exception:
            logger.warning(
                "Memory hydration failed — continuing without agent_memory",
                exc_info=True,
            )

    return builder
```

#### [MODIFY] `core/flow/context.yaml`
Add `specweaver/workspace/memory` to `consumes`.

#### [MODIFY] `tach.toml`
Add `workspace.memory` to `core.flow` depends_on:
```toml
{ path = "src.specweaver.core.flow", depends_on = [
    "src.specweaver.workspace.memory"
] },
```

#### [NEW] `tests/unit/core/flow/handlers/test_build_base_prompt.py`
- Test `_build_base_prompt()` with `db=None` → no `agent_memory` block (fail-safe path)
- Test with `include_rules=True` → constitution + standards added
- Test with `include_rules=False` → constitution + standards NOT added (2-Tier enforcement)
- Test hydration failure (db raises Exception) → WARNING logged, builder returned without memory
- Test skeleton_files passthrough to PromptBuilder constructor
- Test `project_metadata=None` → gracefully skipped (PromptBuilder.add_project_metadata handles None)
- Test logging at INFO for successful hydration, WARNING for failures
- Test two consecutive calls return independent builders (no shared mutable state)

---

### Commit Boundary 2: Workflow Refactoring — Generator, Planner & Reviewer

**Note**: The planner handler (`_generate_plan_artifact`) lives inside `generation.py`, not a separate handler file. All `generation.py` changes are in this boundary.

#### [MODIFY] `core/flow/handlers/generation.py`
- Pre-SF-2 Hotfix: Add `standards=context.standards` to `generate_code()` and `generate_tests()` calls (RN-6)
- `GenerateCodeHandler._execute()`: Call `_build_base_prompt(context, CODE_GEN_INSTRUCTIONS, skeleton_files=...)`, add plan/topology/env_context, pass builder
- `GenerateTestsHandler._execute()`: Same pattern
- `_generate_plan_artifact()`: Call `_build_base_prompt(context, plan_instructions)` (note: the planner uses inline instruction strings, not a module-level constant), pass builder to `planner.generate_plan()`

#### [MODIFY] `workflows/implementation/generator.py`
- `generate_code()`: Replace parameter list (`constitution`, `standards`, `plan`, `topology`, `project_metadata`, `skeleton_files`) with `base_prompt: PromptBuilder`
- `generate_tests()`: Same signature change
- Method bodies just add domain-specific blocks: `add_file()`, `add_artifact_tagging()`, `add_dictator_overrides()`, `add_context(validation_findings)`, `add_context(environment_context)`

#### [MODIFY] `workflows/planning/planner.py`
- Replace parameter list (`constitution`, `standards`, `project_metadata`, `spec_content`, etc.) with `base_prompt: PromptBuilder`
- Method body adds: `add_context(spec_content)`

#### [MODIFY] `core/flow/handlers/review.py`
- Call `_build_base_prompt(context, REVIEW_INSTRUCTIONS, skeleton_files=...)`
- Add topology to builder
- Pass `base_prompt=builder` to `reviewer.review_spec()` / `review_code()`

#### [MODIFY] `workflows/review/reviewer.py`
- Replace parameter list with `base_prompt: PromptBuilder`
- Method body adds: `add_file()`, `add_mentioned_files()`

#### Regression Tests
- Existing tests in `tests/unit/workflows/implementation/test_generator_*.py` must continue passing
- Existing tests in `tests/unit/workflows/review/test_reviewer_*.py` must continue passing
- Existing tests in `tests/unit/workflows/planning/test_planner_*.py` must continue passing
- New test: prompt output with `db=None` is identical to current behavior (minus agent_memory addition)

---

### Commit Boundary 3: Workflow Refactoring — Drafter & Feature Drafter

#### [MODIFY] `core/flow/handlers/draft.py`
- **2-Tier Handover Enforcement**: Call `_build_base_prompt(context, instructions, include_rules=False)`
- This mathematically guarantees the Drafter receives Agent Memory but is strictly isolated from Tier-1 Constitution/Standards rules
- Pass `base_prompt=builder` to drafter methods

#### [MODIFY] `workflows/drafting/drafter.py`
- Replace parameter list with `base_prompt: PromptBuilder`
- Method body adds: `add_context(user_input)`, per-section topology

#### [MODIFY] `workflows/drafting/feature_drafter.py`
- Same pattern as `drafter.py`

#### Regression Tests
- All existing drafter and feature_drafter tests must continue passing

---

### Commit Boundary 4: Integration Tests & Documentation

#### [NEW] `tests/integration/core/flow/handlers/test_prompt_hydration.py`
Integration test with in-memory SQLite:
1. Pre-populate memory bank with tasks (IN_PROGRESS, BLOCKED, DONE with handover)
2. Call `_build_base_prompt()` with real DB session
3. Assert `<context label="agent_memory">` appears in built prompt
4. Assert task titles and handover notes are present
5. Test empty memory bank → no `agent_memory` block
6. Test corrupted handover_context → graceful degradation (WARNING log, no crash)

#### Documentation Updates
- Update `docs/dev_guides/agent_memory_state_tracking.md` — add handler-based prompt assembly examples
- Update `D-INTL-06_design.md` — mark SF-2 in Progress Tracker
- Update `docs/architecture/architecture_reference.md` — document `_build_base_prompt()` pattern in Feature Map

---

## HITL Decisions Resolved (Phase 4)

1. **Decomposer**: Excluded (operates at different abstraction level).
2. **Standards Gap**: Pre-SF-2 hotfix commit, then `_build_base_prompt()` centralizes this fix.
3. **2-Tier Model**: Adopted. Drafter gets memory but NO constitution/standards via `include_rules=False`.
4. **Assembly Return**: Returns `PromptBuilder` (partially built, ready for domain additions).
5. **tach depends_on**: `core.flow` → `workspace.memory` (explicit dependency).
6. **No Cache**: No cache, added to `optimization_backlog.md`.
7. **MCP**: Stays at handler level.
8. **Tests**: Structural assertions, not snapshots.
9. **Architecture**: Inversion of Control via module-level `_build_base_prompt()` in `core.flow.handlers.base` — no `workflows/commons` module (DDD compliance).
10. **Import DAG**: Verified clean — `core.flow` → `workspace.memory` is a new downward dependency, no cycles.
11. **Scenario Handler**: Explicitly excluded — `ScenarioGenerator` doesn't use `PromptBuilder` (RN-11).

---

## Verification Plan

### Automated Tests
1. `pytest tests/unit/core/flow/handlers/test_build_base_prompt.py -v` — all new unit tests pass
2. `pytest tests/integration/core/flow/handlers/test_prompt_hydration.py -v` — integration tests pass
3. `pytest tests/unit/workflows/ -v` — all existing workflow tests pass (regression)
4. `pytest tests/unit/core/flow/handlers/ -v` — all handler tests pass (regression)
5. `tach check` — no architectural boundary violations
6. `mypy src/specweaver/core/flow/handlers/base.py` — type safety
7. `ruff check src/specweaver/core/flow/` — linting clean
8. Full test suite (`pytest`) — all 4600+ tests pass

### Manual Verification
- Inspect prompt output structure. Prompts will NOT be identical to pre-SF-2 (due to standard injection). Assert presence of `<standards>` XML block in Generator prompts.
