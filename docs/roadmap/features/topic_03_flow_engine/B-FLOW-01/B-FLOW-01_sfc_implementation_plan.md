# B-FLOW-01 SF-C — Arbiter + Feedback Loop

**Status**: IMPLEMENTED · **FRs owned**: FR-8, FR-9, FR-10 · **Depends on**: SF-B (COMMITTED
`d79da22`), SF-B2 (polyglot plan; NOT YET COMMITTED when this plan was written) · **Feature ID**:
3.28 (3.28i + 3.28j) · Design: [B-FLOW-01_design.md](B-FLOW-01_design.md) §Sub-features → SF-C

> [!IMPORTANT]
> SF-C MUST NOT be committed before SF-B2 is committed. SF-B2 introduces the
> `StackTraceFilterInterface` that SF-C's arbiter needs for language-aware filtering.

## Goal

The Arbiter + Feedback Loop (FR-8, FR-9, FR-10):

1. **`ArbitrateVerdictHandler`** (`flow/_arbiter.py`) — LLM-driven error attribution. Three-way
   verdict: `code_bug` / `scenario_error` / `spec_ambiguity`.
2. **Vocabulary filter** (`flow/_arbiter.py`) — strips scenario vocabulary from coding agent
   feedback. The coding agent receives: spec clause reference + behavioral expectation + filtered
   stack trace, and NEVER any scenario vocabulary.
3. **Language-aware stack trace filter** — dispatches to `StackTraceFilterInterface` implementations
   (Python, Java, Kotlin, TypeScript, Rust) provided by SF-B2.
4. **`ArbitrateDualPipelineHandler`** (`flow/_dual_pipeline.py`) — fans out coding + scenario
   pipelines in parallel. Delegates from `OrchestrateComponentsHandler` via `params.mode ==
   "dual_pipeline"`.
5. **`scenario_integration.yaml`** — parent pipeline: orchestrate dual fan-out → run scenario tests
   → arbitrate verdict.
6. **`ReadOnlyWorkspaceBoundary`** (`loom/security.py`) — new subclass for arbiter agent (zero write
   grants).
7. **`arbiter_agent` ROLE_INTENTS** (`loom/tools/filesystem/models.py`) — read-only intents only.
8. **New enum values**: `StepAction.ARBITRATE`, `StepTarget.VERDICT`.

Out of scope: multi-session arbitration history; arbiter confidence thresholds; language-specific
scenario converters and stack trace filter implementations (owned by SF-B2; SF-C only consumes the
interface).

## Where it plugs in

**`OrchestrateComponentsHandler` delegation.** `_decompose.py` hardcodes `new_feature.yaml`. Rather
than making it accept a list of pipelines, it delegates to `ArbitrateDualPipelineHandler` when
`step.params.get("mode") == "dual_pipeline"`:

```python
# In OrchestrateComponentsHandler.execute():
if step.params and step.params.get("mode") == "dual_pipeline":
    from specweaver.core.flow._dual_pipeline import ArbitrateDualPipelineHandler
    return await ArbitrateDualPipelineHandler().execute(step, context)
```

No registry conflict — `(ORCHESTRATE, COMPONENTS)` stays registered to
`OrchestrateComponentsHandler`;
callers without a `mode` param use the existing path.

**Arbiter prompt — structured dual-output JSON:**

```
ARBITRATE_INSTRUCTIONS = """
You are a test arbitration agent. Scenario tests have failed for the component described
in the spec below. Your job is to determine WHO is at fault.

## Verdict types
- code_bug: The implementation does not satisfy the spec's behavioral requirements.
- scenario_error: The scenario test setup is incorrect or tests the wrong behavior.
- spec_ambiguity: The spec clause is ambiguous and both interpretations are valid.

## Output format (JSON only — no other text)
{
  "verdict": "<code_bug|scenario_error|spec_ambiguity>",
  "reasoning": "<internal reasoning>",
  "spec_clause": "<e.g. FR-2>",
  "coding_feedback": "<spec-flavored feedback for the coding agent. MUST NOT contain the words: scenario, test_file, yaml, parametrize, convert, or any path containing 'scenarios/'. MUST read like a spec compliance review.>",
  "scenario_feedback": "<behavioral delta report for scenario agent. MUST NOT contain source code, src/ paths, or implementation details.>"
}
"""
```

**Feedback compatibility.** The loop-back reads
`context.feedback[step_name]["findings"]["results"]`.
`ArbitrateVerdictHandler` writes the same structure `ReviewCodeHandler` writes, so
`_extract_prompt_feedback()` consumes it unchanged:
```python
context.feedback["generate_code"] = {
    "from_step": "arbitrate_verdict",
    "findings": {
        "verdict": "code_bug",
        "results": [{"status": "FAIL", "rule_id": spec_clause, "message": coding_feedback}],
    },
}
```

**`ReadOnlyWorkspaceBoundary` bypasses `WorkspaceBoundary.__init__`.** The parent raises
`ValueError` on empty roots, so the subclass must NOT call `super().__init__()`:
```python
class ReadOnlyWorkspaceBoundary(WorkspaceBoundary):
    def __init__(self, api_paths: list[Path]) -> None:
        if not api_paths:
            raise ValueError("ReadOnlyWorkspaceBoundary requires at least one api_path")
        self.roots: list[Path] = []
        self.api_paths = [p.resolve() for p in api_paths]
```

**Scenario test pathing (monorepo safe).** The `run_scenario_tests` step uses `intent="run_tests"`
and `kind="scenario"`. If the target is empty, `ValidateTestsHandler` resolves the path through the
SF-B2 boundaries, so no string template can break Java and Rust builds:

```python
target = step.params.get("target")
if not target:
    from specweaver.core.loom.commons.language._detect import detect_language
    from specweaver.core.loom.commons.language.scenario_converter_factory import ScenarioConverterFactory
    language = detect_language(context.project_path)
    converter = ScenarioConverterFactory.get_converter(language)
    stem = context.spec_path.stem.replace("_spec", "")
    target = str(converter.get_output_path(stem))
```

### SF-C reuse (line refs as of the design)

| Component | Status | Source | Method |
|-----------|--------|--------|--------|
| `Reviewer` / `ReviewResult` / `ReviewVerdict` pattern | 🟡 Adapt | `workflows/review/reviewer.py:33-258` | Clone pattern for `Arbiter`: same LLM prompt → parse verdict → produce findings. Different verdict types. `flow/` consumes `review/` ✅ |
| `PromptBuilder` | 🟢 Reuse | `infrastructure/llm/prompt_builder.py` | Direct import for assembling arbiter context. `flow/` consumes `llm/` ✅ |
| `QARunnerAtom._intent_run_tests()` | 🟢 Reuse | `loom/atoms/qa_runner/atom.py:104-155` | Direct call: `QARunnerAtom.run({"intent": "run_tests", "target": "scenarios/generated/"})`. Zero modifications. `flow/` consumes `loom/atoms/qa_runner` ✅ |
| `_extract_prompt_feedback()` | 🟢 Reuse | `flow/_generation.py:72-90` | Arbiter writes filtered verdict into `context.feedback` using same format → existing coding/scenario handlers automatically consume it on loop-back |
| `ArbitrateVerdictHandler` | 🔴 New | — | ~120 lines: new handler in `flow/_arbiter.py` (follows `ReviewCodeHandler` pattern) |
| Feedback vocabulary filter (NFR-8) | 🔴 New | — | ~80 lines: strips scenario vocabulary from coding agent feedback, rephrases as spec-derived behavioral assertions |

## Changes

### 1. `ReadOnlyWorkspaceBoundary` · [security.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/security.py)

After `WorkspaceBoundary` (~28 new lines):

```python
class ReadOnlyWorkspaceBoundary(WorkspaceBoundary):
    """Workspace boundary for zero-write agents (arbiters, auditors).

    Has no write roots. All accessible paths are in api_paths (read-only).
    Uses validate_path() inherited from WorkspaceBoundary — it already
    checks api_paths when roots is empty.
    """

    def __init__(self, api_paths: list[Path]) -> None:
        if not api_paths:
            msg = "ReadOnlyWorkspaceBoundary requires at least one api_path"
            raise ValueError(msg)
        # Bypass parent __init__ — parent raises ValueError on empty roots
        self.roots: list[Path] = []
        self.api_paths = [p.resolve() for p in api_paths]

    @property
    def is_read_only(self) -> bool:
        """Always True — this boundary has no write roots."""
        return True
```

> [!CAUTION]
> `validate_path()` in `WorkspaceBoundary` already iterates `self.api_paths` when `self.roots` is
> empty. No override needed.

### 2. `arbiter_agent` ROLE_INTENTS · [models.py (filesystem)](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/tools/filesystem/models.py)

Zero write intents — the arbiter reads everything, writes nothing:
```python
"arbiter_agent": frozenset({
    "read_file",
    "list_directory",
    "grep",
    "find_files",
}),
```

### 3. Enum values · [models.py (flow)](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/models.py)

`StepAction`:
```python
ARBITRATE = "arbitrate"
```

`StepTarget`:
```python
VERDICT = "verdict"
```

`VALID_STEP_COMBINATIONS`:
```python
# Arbiter pipeline combos (Feature 3.28 SF-C)
(StepAction.ARBITRATE, StepTarget.VERDICT),
```

### 4. `ArbitrateVerdictHandler` + vocabulary filter · [_arbiter.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_arbiter.py)

New module, ~220 lines.

**`ArbitrateVerdict(enum.StrEnum)`**:
```python
class ArbitrateVerdict(enum.StrEnum):
    CODE_BUG = "code_bug"
    SCENARIO_ERROR = "scenario_error"
    SPEC_AMBIGUITY = "spec_ambiguity"
    ERROR = "error"
```

**`ArbitrateResult(BaseModel)`**:
```python
class ArbitrateResult(BaseModel):
    verdict: ArbitrateVerdict
    reasoning: str = ""
    spec_clause: str = ""
    coding_feedback: str = ""      # LLM-generated, spec-flavored, no scenario vocab
    scenario_feedback: str = ""    # LLM-generated, behavioral delta only
    raw_response: str = ""
```

**`SCENARIO_VOCABULARY: frozenset[str]`** — post-processing guard:
```python
SCENARIO_VOCABULARY: frozenset[str] = frozenset({
    "scenario", "scenarios/", "test_", "_scenarios",
    "yaml", "parametrize", "convert", "ScenarioSet",
    "scenario_validation", "generate_scenarios",
    "scenario_agent", "scenario pipeline",
})
```

**`_guard_coding_feedback(text: str) -> str`** — deterministic safety net: lowercases the text and
checks for banned terms; on a leak, logs a warning and returns a generic spec-flavored fallback;
otherwise returns `text` unchanged.

**`ArbitrateVerdictHandler.execute(step, context)`**:
1. Guard: `context.llm is None` → error
2. Read `context.spec_path` → spec content
3. Read `context.feedback["scenario_test_results"]` → failure text
4. Build `PromptBuilder`: spec (priority 1), failure report (priority 2, filtered by
   `StackTraceFilterInterface` from SF-B2)
5. Call LLM → parse JSON → `ArbitrateResult`
6. Dispatch on verdict:
   - `CODE_BUG` → write to `context.feedback["generate_code"]` (loop-back to coding) →
     `StepStatus.FAILED`
   - `SCENARIO_ERROR` → write to `context.feedback["generate_scenarios"]` (loop-back to scenario) →
     `StepStatus.FAILED`
   - `SPEC_AMBIGUITY` → `StepStatus.WAITING_FOR_INPUT` (HITL park)
   - `ERROR` → `StepStatus.ERROR`
7. All writes to `context.feedback["generate_code"]` pass through `_guard_coding_feedback()`

**`_build_arbiter_dispatcher(context: RunContext) -> ToolDispatcher | None`**:
- Constructs `ReadOnlyWorkspaceBoundary` with all project paths as `api_paths`
- Calls `ToolDispatcher.create_standard_set(boundary, role="arbiter_agent", allowed_tools=["fs"])`

### 5. `ArbitrateDualPipelineHandler` · [_dual_pipeline.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_dual_pipeline.py)

New module, ~110 lines. **`ArbitrateDualPipelineHandler.execute(step, context)`**:
1. Derive `stem` from `context.spec_path.stem.replace("_spec", "")`
2. Load `new_feature.yaml` + `scenario_validation.yaml` from `importlib.resources`
3. Patch both pipeline dicts: set `params.component = stem` on each step
4. Create two isolated `PipelineRunner` instances (same pattern as `OrchestrateComponentsHandler`
   lines 204-214)
5. `asyncio.gather(*[coding_runner.run(...), scenario_runner.run(...)])` — true parallel
6. No scenario test path is hardcoded here; `ValidateTestsHandler` resolves it (Q13)
7. Return `StepStatus.PASSED` if both pass, `StepStatus.FAILED` with details if either fails
8. Log each pipeline status: `logger.info("dual pipeline: coding=%s scenario=%s", ...)`

[_decompose.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_decompose.py) —
delegation at the top of `OrchestrateComponentsHandler.execute()`, ~5 lines, nothing else changes:
```python
if step.params and step.params.get("mode") == "dual_pipeline":
    from specweaver.core.flow._dual_pipeline import ArbitrateDualPipelineHandler
    return await ArbitrateDualPipelineHandler().execute(step, context)
```

### 6. `scenario_integration.yaml` · [scenario_integration.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/pipelines/scenario_integration.yaml)

```yaml
name: scenario_integration
description: >
  Full dual-pipeline integration: runs coding pipeline and scenario pipeline
  in parallel, then executes scenario tests against coding output, and
  invokes arbiter on failures. (Feature 3.28 SF-C)
version: "1.0"

steps:
  - name: generate_contract
    action: generate
    target: contract
    description: "Extract API Protocol from spec Contract section before fan out"

  - name: run_dual_pipelines
    action: orchestrate
    target: components
    description: "Run coding + scenario pipelines in parallel"
    params:
      mode: dual_pipeline
    gate:
      type: auto
      condition: completed
      on_fail: abort

  - name: run_scenario_tests
    action: validate
    target: tests
    description: "Execute scenario-generated test files against coding output"
    params:
      kind: e2e
    gate:
      type: auto
      condition: all_passed
      on_fail: continue

  - name: arbitrate_verdict
    action: arbitrate
    target: verdict
    description: "Arbiter: attribute failures to code bug / scenario error / spec ambiguity"
    gate:
      type: auto
      condition: completed
      on_fail: loop_back
      loop_target: run_dual_pipelines
      max_retries: 3
```

> [!NOTE]
> `on_fail: continue` on `run_scenario_tests` makes the arbiter run even when tests fail — the
> arbiter decides what to do with the failure. If all tests pass, `arbitrate_verdict` is skipped.

### 7. Registration + `ValidateTestsHandler`

[handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers.py) —
imports:
```python
from specweaver.core.flow._arbiter import ArbitrateVerdictHandler
from specweaver.core.flow._dual_pipeline import ArbitrateDualPipelineHandler
```

`StepHandlerRegistry.__init__()`:
```python
(StepAction.ARBITRATE, StepTarget.VERDICT): ArbitrateVerdictHandler(),
```

`__all__`: `"ArbitrateVerdictHandler"`, `"ArbitrateDualPipelineHandler"`.

[_validation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_validation.py)
— in `ValidateTestsHandler.execute()`, resolve `target_path` with the SF-B2
`ScenarioConverterFactory` (~10 lines):
```python
    target = step.params.get("target")

    # If no target specified by the yaml, fallback to interrogating the true polyglot converter
    if not target:
        from specweaver.core.loom.commons.language._detect import detect_language
        from specweaver.core.loom.commons.language.scenario_converter_factory import ScenarioConverterFactory
        
        language = detect_language(context.project_path)
        converter = ScenarioConverterFactory.get_converter(language)
        stem = context.spec_path.stem.replace("_spec", "")
        # Resolve the fully qualified language-aware test path (e.g. src/test/java/...)
        target_path = converter.get_output_path(stem)
        target = str(target_path)
```

### 8. `dispatcher.py` — arbiter agent branch · [dispatcher.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/dispatcher.py)

In `create_standard_set()`, after the `scenario_agent` block (~10 lines):
```python
elif role == "arbiter_agent":
    from specweaver.core.loom.security import ReadOnlyWorkspaceBoundary
    if isinstance(boundary, ReadOnlyWorkspaceBoundary):
        for api_path in boundary.api_paths:
            grants.append(FolderGrant(str(api_path), AccessMode.READ, recursive=True))
    else:
        # Degraded fallback: treat all paths as read-only
        for root in boundary.roots:
            grants.append(FolderGrant(str(root), AccessMode.READ, recursive=True))
        for api_path in boundary.api_paths:
            grants.append(FolderGrant(str(api_path), AccessMode.READ, recursive=True))
```

### Files

| File | Change |
|---|---|
| `src/specweaver/core/flow/_arbiter.py` | new, ~220 lines |
| `src/specweaver/core/flow/_dual_pipeline.py` | new, ~110 lines |
| `src/specweaver/workflows/pipelines/scenario_integration.yaml` | new, ~35 lines |
| `tests/unit/core/flow/test_arbiter.py` | new, ~130 lines |
| `tests/unit/core/flow/test_dual_pipeline.py` | new, ~70 lines |
| `tests/unit/core/flow/test_scenario_integration_yaml.py` | new, ~40 lines |
| `tests/unit/core/loom/test_security_readonly.py` | new, ~55 lines |
| `tests/unit/core/loom/test_dispatcher_arbiter.py` | new, ~40 lines |
| `tests/integration/core/flow/test_arbiter_integration.py` | new, ~90 lines |
| `src/specweaver/core/loom/security.py` | +28 lines |
| `src/specweaver/core/loom/dispatcher.py` | +10 lines |
| `src/specweaver/core/loom/tools/filesystem/models.py` | +5 lines |
| `src/specweaver/core/flow/models.py` | +3 lines |
| `src/specweaver/core/flow/handlers.py` | +6 lines |
| `src/specweaver/core/flow/_decompose.py` | +5 lines |
| `src/specweaver/core/flow/_validation.py` | +7 lines |
| `tests/unit/core/flow/test_models.py` | +3 lines |

Commit: `feat(3.28i-j): add arbiter handler, dual-pipeline orchestrator, and scenario integration
pipeline`

## Tests

Unit:

`tests/unit/core/loom/test_security_readonly.py` — class `TestReadOnlyWorkspaceBoundary`:
- `test_requires_api_paths` — empty list raises `ValueError`
- `test_is_read_only` — `True`
- `test_roots_is_empty` — `boundary.roots == []`
- `test_validate_path_within_api_path` — allowed path → success
- `test_validate_path_outside_boundary` — raises `WorkspaceBoundaryError`
- `test_regular_boundary_still_rejects_empty_roots` — `WorkspaceBoundary(roots=[])` still raises

`tests/unit/core/flow/test_arbiter.py`:

Class `TestArbitrateVerdict`:
- `test_all_verdict_values` — all 4 present in enum

Class `TestArbitrateResult`:
- `test_model_validation` — Pydantic roundtrip with all fields

Class `TestVocabularyGuard`:
- `test_clean_feedback_unchanged`
- `test_leaked_scenario_term_triggers_fallback`
- `test_leaked_scenarios_path_triggers_fallback`
- `test_case_insensitive_detection` — "Scenario" caught
- `test_multiple_leaks_triggers_single_fallback`

Class `TestArbitrateVerdictHandler`:
- `test_code_bug_writes_to_generate_code_feedback`
- `test_code_bug_feedback_has_no_scenario_vocab`
- `test_scenario_error_writes_to_generate_scenarios_feedback`
- `test_spec_ambiguity_returns_waiting_for_input`
- `test_no_llm_returns_error`
- `test_handler_registered_in_registry`
- `test_arbitrate_verdict_in_valid_combinations`

`tests/unit/core/flow/test_dual_pipeline.py` — class `TestArbitrateDualPipelineHandler`:
- `test_fans_out_both_pipelines`
- `test_returns_failed_if_coding_fails`
- `test_returns_failed_if_scenario_fails`
- `test_stores_scenario_test_path_in_feedback`
- `test_stem_derived_from_spec_path`
- `test_logging_on_completion`

`tests/unit/core/flow/test_scenario_integration_yaml.py` — class `TestScenarioIntegrationPipeline`:
- `test_pipeline_loads`
- `test_step_count` — 3 steps
- `test_dual_pipeline_mode_param`
- `test_arbitrate_step_gate`

`tests/unit/core/flow/test_models.py`:
- `StepAction` count: current → +1 (`ARBITRATE`)
- `StepTarget` count: current → +1 (`VERDICT`)
- `VALID_STEP_COMBINATIONS` count: +1

`tests/unit/core/loom/test_dispatcher_arbiter.py`:
- `test_arbiter_agent_in_role_intents`
- `test_arbiter_agent_has_no_write_intents`
- `test_create_standard_set_arbiter_uses_read_only_grants`

Integration — `tests/integration/core/flow/test_arbiter_integration.py`, class
`TestArbitrateFeedbackLoop`:
- `test_code_bug_feedback_reaches_generate_code_handler` — full context roundtrip
- `test_nfr8_no_scenario_vocab_in_coding_feedback` — mock LLM → assert banned terms absent in
  `context.feedback["generate_code"]`
- `test_scenario_error_feedback_reaches_generate_scenarios_handler`
- `test_spec_ambiguity_parks_run`

```
pytest tests/unit/core/flow/test_arbiter.py -v
pytest tests/unit/core/flow/test_dual_pipeline.py -v
pytest tests/unit/core/flow/test_scenario_integration_yaml.py -v
pytest tests/unit/core/loom/test_security_readonly.py -v
pytest tests/unit/core/loom/test_dispatcher_arbiter.py -v
pytest tests/integration/core/flow/test_arbiter_integration.py -v
pytest tests/unit/core/flow/test_models.py -v
python -m tach check
ruff check src/ tests/
mypy src/ tests/
pytest tests/ -v --tb=short   # full regression
```

Key assertions:
- `ArbitrateVerdict` has 4 values
- `(ARBITRATE, VERDICT)` in `VALID_STEP_COMBINATIONS`
- `"arbiter_agent"` in `ROLE_INTENTS` with zero write intents
- `scenario_integration.yaml` round-trips through `PipelineDefinition`
- `ReadOnlyWorkspaceBoundary.is_read_only == True`
- `_guard_coding_feedback()` catches all 10+ scenario vocabulary terms

## Decisions (audit, all resolved)

| Q# | Topic | Decision |
|----|-------|----------|
| Q1 | Dual-pipeline orchestrator | **Option C** — new `ArbitrateDualPipelineHandler`; delegates via `OrchestrateComponentsHandler` mode param |
| Q2 | Post-JOIN trigger mechanism | **Option A** — `scenario_integration.yaml` parent pipeline |
| Q3 | `WorkspaceBoundary` empty roots | **Option C** — new `ReadOnlyWorkspaceBoundary` subclass |
| Q4 | Arbiter verdict type | **Option A** — new `ArbitrateVerdict` + `ArbitrateResult` |
| Q5 | Vocabulary filter approach | **Option C** — structured LLM JSON with dual `coding_feedback`/`scenario_feedback` + word-list guard |
| Q6 | NFR-5 retries | **Option A** — gate `max_retries: 3` in `scenario_integration.yaml` |
| Q7 | New enums | `ARBITRATE` + `VERDICT` added |
| Q8 | Parent pipeline name | `scenario_integration.yaml` |
| Q9 | Arbiter agent role | `arbiter_agent` in `ROLE_INTENTS`, read-only intents |
| Q10 | Handler location | `flow/_arbiter.py` |
| Q11 | Test strategy | Unit (vocab filter) + Integration (handler pipeline) |
| Q12 | Monorepo scope | Dynamic path resolution via `ScenarioConverterFactory.get_converter(lang).get_output_path(stem)` |
| Q13 | Scenario test runner | Reuse `ValidateTestsHandler` with `kind: scenario` (delegates pathing internally to Atom) |
| Q14 | Documentation | Pre-commit phase 6; update `docs/dev_guides/scenario_pipelines.md` |
| Q15 | `WorkspaceBoundary` tests | Update assertions: `ValueError` only when both `roots=[]` AND `api_paths=[]` |

**Stack traces.** FR-9 lets the coding agent see its own stack trace. `ArbitrateVerdictHandler` uses
`StackTraceFilterInterface` (SF-B2) to strip scenario file path frames and keep only frames from
the project's source directory. Frame formats per language:

| Language | Scenario frame pattern | Source frame pattern |
|----------|----------------------|---------------------|
| Python | `scenarios/generated/test_*.py:N` | `src/**/*.py:N in func` |
| Java | `scenarios.generated.Test*` (package) | `com.example.**:N` |
| Kotlin | `scenarios.generated.Test*Kt` | `com.example.**:N` |
| TypeScript | `scenarios/generated/test_*.ts:N` | `src/**/*.ts:N` |
| Rust | `scenario_tests::` (module) | `crate::module::func` |

**Deviations from the design:**

| Item | Design Says | This Plan Says | Reason |
|------|------------|---------------|--------|
| `flow/_arbiter.py` module | `flow/` | `flow/_arbiter.py` | Follows naming convention of `_review.py`, `_scenario.py` |
| Stack trace filtering | "vocabulary filter" (unspecified) | `StackTraceFilterInterface` from SF-B2 | Language-aware filtering is mandatory (user requirement) |
| `WorkspaceBoundary` for arbiter | `roots=[]` | `ReadOnlyWorkspaceBoundary` subclass | Clean SRP; avoids patching existing class constructor |

## As built

**Since moved** (noted 2026-09-25): handlers are in `core/flow/handlers/` (`arbiter.py`,
`dual_pipeline.py`, `validation.py`); `ReadOnlyWorkspaceBoundary` is in `sandbox/security.py`.
`ValidateTestsHandler` resolves the target with `create_scenario_converter(context.project_path)`
and `output_path()` — there is no `ScenarioConverterFactory` class. `scenario_integration.yaml` sets
`kind: scenario` on `run_scenario_tests` and adds `max_retries_hitl: 4`.
