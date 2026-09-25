# D-INTL-06 SF-02 — Prompt Assembly via Inversion of Control

**Status**: DRAFT (implemented and committed — see the design's Progress Tracker) · **FRs owned**:
FR-6, FR-7 · **NFRs**: NFR-2, NFR-5, NFR-6, NFR-7, NFR-8, NFR-9 · **Depends on**: SF-01 · Design:
[D-INTL-06_design.md](D-INTL-06_design.md) §Sub-features → SF-02

**Since moved** (2026-08-12, `0f5f16b9`): `_build_base_prompt()` lives in
`core/flow/handlers/prompting.py`, re-exported from `base`; `include_rules` became
`profile: RenderProfile` (`C-INTL-05`). Line refs below are as of the plan's date.

## Goal

A module-level async function `_build_base_prompt()` in `core.flow.handlers.base` builds the base
`PromptBuilder` (instructions, project metadata, constitution, standards, memory hydration). Each
handler passes it down to its Domain Layer workflow method, which adds only its domain-specific
blocks. Removes a ~150-line DRY violation and gives future context sources one integration point,
without a `workflows/commons` module (which would break DDD bounded context isolation).

## Where it plugs in

| # | Fact | Source |
|---|---|---|
| RN-1 | There are **6 files** with PromptBuilder usage, not 5: `generator.py` — `generate_code()` + `generate_tests()` (2 call sites); `reviewer.py` — `review_spec()` + `review_code()` (2); `planner.py` — `generate_plan()` (1); `drafter.py` — `_generate_section()` (1); `feature_drafter.py` — `_generate_section()` (1); `decomposer.py` — `decompose()` (1). `decomposer.py` is **minimal** (no constitution, no standards, no plan, no skeleton_files) and builds a structural architecture map, not code — **excluded** (HITL). | `workflows/planning/decomposer.py:83-97` |
| RN-3 | `PromptBuilder.add_context()` signature verified (below); called as `builder.add_context(block, "agent_memory", priority=2)`. | `infrastructure/llm/prompt_builder.py:178-201` |
| RN-4 | `RunContext` already has `context.db: Any = None` (line 60) and `context.project_path: Path` (required, line 45) — no parameter threading needed. | `core/flow/handlers/base.py:28-71` |
| RN-5 | `core.flow` has `depends_on = []`; `workspace.memory` already exposes `hydrator` (line 243-244). Add `src.specweaver.workspace.memory` to `core.flow`'s `depends_on`. | `tach.toml:15` |
| RN-6 | The generator handler passed `constitution=context.constitution` but not `standards=context.standards` (lines 146-158 `generate_code()`, lines 236-250 `generate_tests()`); `_generate_plan_artifact()` (line 352-361) and the reviewer passed both. A pre-SF-02 hotfix added it to `GenerateCodeHandler._execute()` and `GenerateTestsHandler._execute()`; `_build_base_prompt()` now always adds standards. | `core/flow/handlers/generation.py:146-158` |
| RN-7 | DB access pattern from handlers (below); `_build_base_prompt()` must be `async` to use `async with`. | `core/flow/handlers/generation.py:163-172` |
| RN-8 | `ArbiterHandler` builds raw `Message` prompts, no `PromptBuilder` — exclusion is correct. | `core/flow/handlers/arbiter.py` |
| RN-9 | `core.flow` consumes `specweaver/config`, `specweaver/llm`, `specweaver/review`, `specweaver/implementation`, `specweaver/planning`, `specweaver/validation` and several sandbox modules — not `specweaver/workspace/memory`, which is added. No workflow `context.yaml` changes: workflows get a pre-built `PromptBuilder` and never import `workspace.memory`. | `core/flow/context.yaml:18-31` |
| RN-10 | All 5 workflow modules import `PromptBuilder` inline (acknowledged anti-pattern in the architecture reference, used to break circular imports). `_build_base_prompt()` imports `PromptBuilder` and `MemoryHydrator` inline too. | — |
| RN-11 | `ScenarioGenerator.generate_scenarios()` builds a raw string via static `_build_prompt()` and calls `self._llm.generate(prompt)`; its handler (`core/flow/handlers/scenario.py`) passes `constitution` and `project_metadata` directly. Out of scope. | `workflows/scenarios/scenario_generator.py:47-86, 183-227` |

RN-7 pattern:

```python
if context.db:
    async with context.db.async_session_scope() as session:
        # ... use session ...
```

RN-3 signature:

```python
def add_context(self, text: str, label: str, *, priority: int = 3) -> PromptBuilder:
```

**RN-2 — assembly chain per module:**

| Module | instructions | project_metadata | file | constitution | standards | plan | topology | env_context | skeleton_files | dictator | validation | mentioned_files |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| generator.generate_code | ✅ | ✅ | ✅ | ✅ | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| generator.generate_tests | ✅ | ✅ | ✅ | ✅ | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| reviewer.review_spec | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| reviewer.review_code | ✅ | ✅ | ✅✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| planner.generate_plan | ✅✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| drafter._generate_section | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| feature_drafter._generate_section | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

So `_build_base_prompt()` produces the **base** (instructions + project_metadata + constitution +
standards + memory context); the handler adds handler-specific blocks (plan, topology,
skeleton_files); the workflow method adds domain blocks (file, dictator, validation, etc.).

**RN-12 — all 16 handler files in `core/flow/handlers/`:**

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

## Changes

### CB-1 — Foundation: `_build_base_prompt()`

1. **`core/flow/handlers/base.py`** — a module-level async function (there is no `BaseHandler`
   class; `base.py` defines `RunContext` and the `StepHandler` protocol):

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

2. **`core/flow/context.yaml`** — add `specweaver/workspace/memory` to `consumes`.
3. **`tach.toml`** — add `workspace.memory` to `core.flow` depends_on:

```toml
{ path = "src.specweaver.core.flow", depends_on = [
    "src.specweaver.workspace.memory"
] },
```

### CB-2 — Generator, Planner & Reviewer

The planner handler (`_generate_plan_artifact`) lives inside `generation.py`, so all
`generation.py` changes are here.

4. **`core/flow/handlers/generation.py`**
   - Pre-SF-02 hotfix: add `standards=context.standards` to the `generate_code()` and
     `generate_tests()` calls (RN-6).
   - `GenerateCodeHandler._execute()`: `_build_base_prompt(context, CODE_GEN_INSTRUCTIONS, skeleton_files=...)`,
     add plan/topology/env_context, pass the builder. `GenerateTestsHandler._execute()`: same.
   - `_generate_plan_artifact()`: `_build_base_prompt(context, plan_instructions)` (the planner uses
     inline instruction strings, not a module constant), pass the builder to `planner.generate_plan()`.
5. **`workflows/implementation/generator.py`** — `generate_code()` and `generate_tests()` replace
   (`constitution`, `standards`, `plan`, `topology`, `project_metadata`, `skeleton_files`) with
   `base_prompt: PromptBuilder`; bodies add only `add_file()`, `add_artifact_tagging()`,
   `add_dictator_overrides()`, `add_context(validation_findings)`, `add_context(environment_context)`.
6. **`workflows/planning/planner.py`** — replace (`constitution`, `standards`, `project_metadata`,
   `spec_content`, etc.) with `base_prompt: PromptBuilder`; body adds `add_context(spec_content)`.
7. **`core/flow/handlers/review.py`** — `_build_base_prompt(context, REVIEW_INSTRUCTIONS, skeleton_files=...)`,
   add topology, pass `base_prompt=builder` to `reviewer.review_spec()` / `review_code()`.
8. **`workflows/review/reviewer.py`** — `base_prompt: PromptBuilder`; body adds `add_file()`,
   `add_mentioned_files()`.

### CB-3 — Drafter & Feature Drafter

9. **`core/flow/handlers/draft.py`** — **2-Tier Handover**:
   `_build_base_prompt(context, instructions, include_rules=False)`, so the Drafter gets Agent
   Memory but never Tier-1 Constitution/Standards; pass `base_prompt=builder`.
10. **`workflows/drafting/drafter.py`** — `base_prompt: PromptBuilder`; body adds
    `add_context(user_input)` and per-section topology.
11. **`workflows/drafting/feature_drafter.py`** — same as `drafter.py`.

### CB-4 — Integration tests & docs

12. Docs: `docs/dev_guides/agent_memory_state_tracking.md` (handler-based prompt assembly
    examples); `D-INTL-06_design.md` (Progress Tracker); `docs/architecture/architecture_reference.md`
    (`_build_base_prompt()` pattern in the Feature Map).

**Modified files:**

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

**NOT modified:**

- `RunContext` (no new fields — `db` and `project_path` already exist)
- `PromptBuilder` (no new methods — uses existing `add_context()`)
- `interfaces/cli/*` (no CLI changes)
- `interfaces/api/*` (no API changes)
- `ArbiterHandler` (uses minimal prompt via raw `Message` — excluded per FR-6)
- `workflows/planning/decomposer.py` (Excluded per HITL Phase 4 — operates at different abstraction level)
- `workflows/scenarios/scenario_generator.py` (Does NOT use `PromptBuilder` — builds raw string prompts directly. No refactoring needed.)
- All workflow `context.yaml` files (no new domain dependencies introduced)

## Tests

| Tier | File | Cases |
|---|---|---|
| Unit (CB-1) | `tests/unit/core/flow/handlers/test_build_base_prompt.py` (NEW) | `db=None` → no `agent_memory` block (fail-safe path); `include_rules=True` → constitution + standards added; `include_rules=False` → not added (2-Tier); db raises Exception → WARNING logged, builder returned without memory; skeleton_files passed to the PromptBuilder constructor; `project_metadata=None` → skipped (PromptBuilder.add_project_metadata handles None); INFO on successful hydration, WARNING on failure; two consecutive calls return independent builders (no shared mutable state) |
| Regression (CB-2) | `tests/unit/workflows/implementation/test_generator_*.py`, `tests/unit/workflows/review/test_reviewer_*.py`, `tests/unit/workflows/planning/test_planner_*.py` | keep passing; new: prompt with `db=None` identical to current behavior (minus agent_memory addition) |
| Regression (CB-3) | drafter and feature_drafter tests | keep passing |
| Integration (CB-4) | `tests/integration/core/flow/handlers/test_prompt_hydration.py` (NEW), in-memory SQLite | 1. pre-populate tasks (IN_PROGRESS, BLOCKED, DONE with handover); 2. call `_build_base_prompt()` with a real DB session; 3. `<context label="agent_memory">` in the built prompt; 4. task titles and handover notes present; 5. empty memory bank → no `agent_memory` block; 6. corrupted handover_context → WARNING, no crash |

Commands:

1. `pytest tests/unit/core/flow/handlers/test_build_base_prompt.py -v` — all new unit tests pass
2. `pytest tests/integration/core/flow/handlers/test_prompt_hydration.py -v` — integration tests pass
3. `pytest tests/unit/workflows/ -v` — all existing workflow tests pass (regression)
4. `pytest tests/unit/core/flow/handlers/ -v` — all handler tests pass (regression)
5. `tach check` — no architectural boundary violations
6. `mypy src/specweaver/core/flow/handlers/base.py` — type safety
7. `ruff check src/specweaver/core/flow/` — linting clean
8. Full test suite (`pytest`) — all 4600+ tests pass

Manual: inspect the prompt structure. Prompts are NOT identical to pre-SF-02 (standards are now
injected) — assert a `<standards>` XML block in Generator prompts.

## Decisions (audit)

1. **Decomposer**: Excluded (operates at different abstraction level).
2. **Standards Gap**: Pre-SF-02 hotfix commit, then `_build_base_prompt()` centralizes this fix.
3. **2-Tier Model**: Adopted. Drafter gets memory but NO constitution/standards via `include_rules=False`.
4. **Assembly Return**: Returns `PromptBuilder` (partially built, ready for domain additions).
5. **tach depends_on**: `core.flow` → `workspace.memory` (explicit dependency).
6. **No Cache**: No cache, added to `optimization_backlog.md`.
7. **MCP**: Stays at handler level.
8. **Tests**: Structural assertions, not snapshots.
9. **Architecture**: Inversion of Control via module-level `_build_base_prompt()` in `core.flow.handlers.base` — no `workflows/commons` module (DDD compliance).
10. **Import DAG**: Verified clean — `core.flow` → `workspace.memory` is a new downward dependency, no cycles.
11. **Scenario Handler**: Explicitly excluded — `ScenarioGenerator` doesn't use `PromptBuilder` (RN-11).
