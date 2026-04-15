# Implementation Plan: Scenario Testing — Independent Verification [SF-C: Arbiter + Feedback Loop]

- **Feature ID**: 3.28
- **Sub-Feature**: SF-C — Arbiter + Feedback Loop (3.28i + 3.28j)
- **Design Document**: docs/roadmap/phase_3/feature_3.28/feature_3.28_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-C
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.28/feature_3.28_sfc_implementation_plan.md
- **Status**: DRAFT
- **Depends on**: SF-B (COMMITTED `d79da22`), SF-B2 (polyglot plan, NOT YET COMMITTED)

> [!IMPORTANT]
> SF-C MUST NOT be committed before SF-B2 is committed. SF-B2 introduces the
> `StackTraceFilterInterface` that SF-C's arbiter needs for language-aware filtering.

---

## Scope

SF-C delivers the Arbiter + Feedback Loop (FR-8, FR-9, FR-10):

1. **`ArbitrateVerdictHandler`** (`flow/_arbiter.py`) — LLM-driven error attribution. Three-way verdict: `code_bug` / `scenario_error` / `spec_ambiguity`.
2. **Vocabulary filter** (`flow/_arbiter.py`) — strips scenario vocabulary from coding agent feedback. Coding agent receives: spec clause reference + behavioral expectation + filtered stack trace. Coding agent NEVER receives any scenario vocabulary.
3. **Language-aware stack trace filter** — dispatches to `StackTraceFilterInterface` implementations (Python, Java, Kotlin, TypeScript, Rust) provided by SF-B2.
4. **`ArbitrateDualPipelineHandler`** (`flow/_dual_pipeline.py`) — fans out coding + scenario pipelines in parallel. Delegates from `OrchestrateComponentsHandler` via `params.mode == "dual_pipeline"`.
5. **`scenario_integration.yaml`** — parent pipeline: orchestrate dual fan-out → run scenario tests → arbitrate verdict.
6. **`ReadOnlyWorkspaceBoundary`** (`loom/security.py`) — new subclass for arbiter agent (zero write grants).
7. **`arbiter_agent` ROLE_INTENTS** (`loom/tools/filesystem/models.py`) — read-only intents only.
8. **New enum values**: `StepAction.ARBITRATE`, `StepTarget.VERDICT`.

### What's Out of Scope
- Multi-session arbitration history
- Arbiter confidence thresholds
- Language-specific scenario converters (owned by SF-B2)
- Stack trace filter implementations (owned by SF-B2; SF-C only consumes via interface)

---

## HITL Gate Decisions (All Resolved)

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
| Q12 | Monorepo scope | Target = specific file `test_{stem}_scenarios.{ext}` from `context.spec_path` |
| Q13 | Scenario test runner | Reuse `ValidateTestsHandler` with `target_path_template` param |
| Q14 | Documentation | Pre-commit phase 6; update `docs/dev_guides/scenario_pipelines.md` |
| Q15 | `WorkspaceBoundary` tests | Update assertions: `ValueError` only when both `roots=[]` AND `api_paths=[]` |

### Additional Resolution: Stack Trace Handling

The coding agent receives its own stack trace (FR-9 explicitly allows it). The `ArbitrateVerdictHandler` uses `StackTraceFilterInterface` (provided by SF-B2) to strip scenario file path frames, keeping only frames from the project's source directory. Language frame format differs per language:

| Language | Scenario frame pattern | Source frame pattern |
|----------|----------------------|---------------------|
| Python | `scenarios/generated/test_*.py:N` | `src/**/*.py:N in func` |
| Java | `scenarios.generated.Test*` (package) | `com.example.**:N` |
| Kotlin | `scenarios.generated.Test*Kt` | `com.example.**:N` |
| TypeScript | `scenarios/generated/test_*.ts:N` | `src/**/*.ts:N` |
| Rust | `scenario_tests::` (module) | `crate::module::func` |

---

## Research Notes

### RN-1: `OrchestrateComponentsHandler` delegation strategy

`_decompose.py` hardcodes `new_feature.yaml`. Rather than modifying it to accept a list of pipelines, `ArbitrateDualPipelineHandler` is invoked when `step.params.get("mode") == "dual_pipeline"`. The existing handler checks for this param and delegates:

```python
# In OrchestrateComponentsHandler.execute():
if step.params and step.params.get("mode") == "dual_pipeline":
    from specweaver.core.flow._dual_pipeline import ArbitrateDualPipelineHandler
    return await ArbitrateDualPipelineHandler().execute(step, context)
```

No registry conflict — `(ORCHESTRATE, COMPONENTS)` remains registered to `OrchestrateComponentsHandler`. All existing callers (no `mode` param) use the existing code path.

### RN-2: Arbiter prompt — structured dual-output JSON

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

### RN-3: `_extract_prompt_feedback()` compatibility

The loop-back mechanism reads `context.feedback[step_name]["findings"]["results"]`. `ArbitrateVerdictHandler` writes:
```python
context.feedback["generate_code"] = {
    "from_step": "arbitrate_verdict",
    "findings": {
        "verdict": "code_bug",
        "results": [{"status": "FAIL", "rule_id": spec_clause, "message": coding_feedback}],
    },
}
```
This is structurally identical to what `ReviewCodeHandler` writes → `_extract_prompt_feedback()` consumes it unchanged.

### RN-4: `ReadOnlyWorkspaceBoundary` bypasses `WorkspaceBoundary.__init__`

The subclass must NOT call `super().__init__()` since the parent raises `ValueError` on empty roots. Bypass explicitly:
```python
class ReadOnlyWorkspaceBoundary(WorkspaceBoundary):
    def __init__(self, api_paths: list[Path]) -> None:
        if not api_paths:
            raise ValueError("ReadOnlyWorkspaceBoundary requires at least one api_path")
        self.roots: list[Path] = []
        self.api_paths = [p.resolve() for p in api_paths]
```

### RN-5: Scenario test file path construction (monorepo safe)

The `run_scenario_tests` step uses `target_path_template`. `ValidateTestsHandler` substitutes `{stem}` at runtime from `context.spec_path`. SF-B2 determines the file extension (`{ext}`) based on language. The handler must also support `{ext}`:

```python
template = step.params.get("target_path_template", "")
stem = context.spec_path.stem.replace("_spec", "")
ext = _detect_test_extension(context.project_path)  # provided by SF-B2 helper
target_path = template.replace("{stem}", stem).replace("{ext}", ext)
```

`ValidateTestsHandler` needs this small extension.

---

## Component Breakdown

---

### Component 1: `ReadOnlyWorkspaceBoundary`

#### [MODIFY] [security.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/security.py)

Add after `WorkspaceBoundary` class (~28 new lines):

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
> `validate_path()` in `WorkspaceBoundary` already iterates `self.api_paths` when
> `self.roots` is empty. No override needed — the existing logic works correctly.

---

### Component 2: `arbiter_agent` ROLE_INTENTS

#### [MODIFY] [models.py (filesystem)](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/tools/filesystem/models.py)

Add to `ROLE_INTENTS` dict:
```python
"arbiter_agent": frozenset({
    "read_file",
    "list_directory",
    "grep",
    "find_files",
}),
```
Zero write intents. Arbiter reads everything, writes nothing.

---

### Component 3: New enum values

#### [MODIFY] [models.py (flow)](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/models.py)

Add to `StepAction`:
```python
ARBITRATE = "arbitrate"
```

Add to `StepTarget`:
```python
VERDICT = "verdict"
```

Add to `VALID_STEP_COMBINATIONS`:
```python
# Arbiter pipeline combos (Feature 3.28 SF-C)
(StepAction.ARBITRATE, StepTarget.VERDICT),
```

---

### Component 4: `ArbitrateVerdictHandler` + vocabulary filter

#### [NEW] [_arbiter.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_arbiter.py)

~220 lines. Full module:

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

**`_guard_coding_feedback(text: str) -> str`** — deterministic safety net:
- Lowercases text, checks for banned terms
- On leak detected: logs warning, returns generic spec-flavored fallback
- Returns original `text` if clean

**`ArbitrateVerdictHandler.execute(step, context)`**:
1. Guard: `context.llm is None` → error
2. Read `context.spec_path` → spec content
3. Read `context.feedback["scenario_test_results"]` → failure text
4. Build `PromptBuilder`: spec (priority 1), failure report (priority 2, filtered by `StackTraceFilterInterface` from SF-B2)
5. Call LLM → parse JSON → `ArbitrateResult`
6. Dispatch on verdict:
   - `CODE_BUG` → write to `context.feedback["generate_code"]` (loop-back to coding) → `StepStatus.FAILED`
   - `SCENARIO_ERROR` → write to `context.feedback["generate_scenarios"]` (loop-back to scenario) → `StepStatus.FAILED`
   - `SPEC_AMBIGUITY` → `StepStatus.WAITING_FOR_INPUT` (HITL park)
   - `ERROR` → `StepStatus.ERROR`
7. All writes to `context.feedback["generate_code"]` pass through `_guard_coding_feedback()`

**`_build_arbiter_dispatcher(context: RunContext) -> ToolDispatcher | None`**:
- Constructs `ReadOnlyWorkspaceBoundary` with all project paths as `api_paths`
- Calls `ToolDispatcher.create_standard_set(boundary, role="arbiter_agent", allowed_tools=["fs"])`

---

### Component 5: `ArbitrateDualPipelineHandler`

#### [NEW] [_dual_pipeline.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_dual_pipeline.py)

~110 lines.

**`ArbitrateDualPipelineHandler.execute(step, context)`**:
1. Derive `stem` from `context.spec_path.stem.replace("_spec", "")`
2. Load `new_feature.yaml` + `scenario_validation.yaml` from `importlib.resources`
3. Patch both pipeline dicts: set `params.component = stem` on each step
4. Create two isolated `PipelineRunner` instances (same pattern as `OrchestrateComponentsHandler` lines 204-214)
5. `asyncio.gather(*[coding_runner.run(...), scenario_runner.run(...)])` — true parallel
6. Store the scenario test file path in `context.feedback`:
   ```python
   ext = detect_scenario_extension(context.project_path)  # from SF-B2
   context.feedback["scenario_test_path"] = str(
       context.project_path / "scenarios" / "generated" / f"test_{stem}_scenarios.{ext}"
   )
   ```
7. Return `StepStatus.PASSED` if both pass, `StepStatus.FAILED` with details if either fails
8. Log each pipeline status: `logger.info("dual pipeline: coding=%s scenario=%s", ...)`

#### [MODIFY] [_decompose.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_decompose.py)

Add delegation at top of `OrchestrateComponentsHandler.execute()`:
```python
if step.params and step.params.get("mode") == "dual_pipeline":
    from specweaver.core.flow._dual_pipeline import ArbitrateDualPipelineHandler
    return await ArbitrateDualPipelineHandler().execute(step, context)
```
~5 lines. No other changes to `_decompose.py`.

---

### Component 6: `scenario_integration.yaml`

#### [NEW] [scenario_integration.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/pipelines/scenario_integration.yaml)

```yaml
name: scenario_integration
description: >
  Full dual-pipeline integration: runs coding pipeline and scenario pipeline
  in parallel, then executes scenario tests against coding output, and
  invokes arbiter on failures. (Feature 3.28 SF-C)
version: "1.0"

steps:
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
      target_path_template: "scenarios/generated/test_{stem}_scenarios.{ext}"
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
> `on_fail: continue` on `run_scenario_tests` ensures the arbiter always runs after
> tests — even when tests fail. The arbiter is the one that decides what to do with
> the failure. If all tests pass, `arbitrate_verdict` is skipped (no action needed).

---

### Component 7: Handler registration + `ValidateTestsHandler` extension

#### [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers.py)

Add import and registry entry:
```python
from specweaver.core.flow._arbiter import ArbitrateVerdictHandler
from specweaver.core.flow._dual_pipeline import ArbitrateDualPipelineHandler
```

Add to `StepHandlerRegistry.__init__()`:
```python
(StepAction.ARBITRATE, StepTarget.VERDICT): ArbitrateVerdictHandler(),
```

Add to `__all__`: `"ArbitrateVerdictHandler"`, `"ArbitrateDualPipelineHandler"`.

#### [MODIFY] [_validation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_validation.py)

In `ValidateTestsHandler.execute()`, extend `target_path` resolution to support `{stem}` and `{ext}` templates:
```python
target_param = step.params.get("target_path") or step.params.get("target_path_template")
if target_param and ("{stem}" in target_param or "{ext}" in target_param):
    from specweaver.core.loom.commons.language.scenario_converter_factory import detect_scenario_extension
    stem = context.spec_path.stem.replace("_spec", "")
    ext = detect_scenario_extension(context.project_path)
    target_param = target_param.replace("{stem}", stem).replace("{ext}", ext)
```
~7 lines. Requires SF-B2's `detect_scenario_extension()` helper.

---

### Component 8: `dispatcher.py` — arbiter agent branch

#### [MODIFY] [dispatcher.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/dispatcher.py)

In `create_standard_set()`, add `arbiter_agent` branch after `scenario_agent` block:
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
~10 lines.

---

## Test Plan

### Unit Tests

#### [NEW] tests/unit/core/loom/test_security_readonly.py

Class `TestReadOnlyWorkspaceBoundary`:
- `test_requires_api_paths` — empty list raises `ValueError`
- `test_is_read_only` — `True`
- `test_roots_is_empty` — `boundary.roots == []`
- `test_validate_path_within_api_path` — allowed path → success
- `test_validate_path_outside_boundary` — raises `WorkspaceBoundaryError`
- `test_regular_boundary_still_rejects_empty_roots` — `WorkspaceBoundary(roots=[])` still raises

#### [NEW] tests/unit/core/flow/test_arbiter.py

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

#### [NEW] tests/unit/core/flow/test_dual_pipeline.py

Class `TestArbitrateDualPipelineHandler`:
- `test_fans_out_both_pipelines`
- `test_returns_failed_if_coding_fails`
- `test_returns_failed_if_scenario_fails`
- `test_stores_scenario_test_path_in_feedback`
- `test_stem_derived_from_spec_path`
- `test_logging_on_completion`

#### [NEW] tests/unit/core/flow/test_scenario_integration_yaml.py

Class `TestScenarioIntegrationPipeline`:
- `test_pipeline_loads`
- `test_step_count` — 3 steps
- `test_dual_pipeline_mode_param`
- `test_arbitrate_step_gate`

#### [MODIFY] tests/unit/core/flow/test_models.py
- `StepAction` count: current → +1 (`ARBITRATE`)
- `StepTarget` count: current → +1 (`VERDICT`)
- `VALID_STEP_COMBINATIONS` count: +1

#### [NEW] tests/unit/core/loom/test_dispatcher_arbiter.py
- `test_arbiter_agent_in_role_intents`
- `test_arbiter_agent_has_no_write_intents`
- `test_create_standard_set_arbiter_uses_read_only_grants`

### Integration Tests

#### [NEW] tests/integration/core/flow/test_arbiter_integration.py

Class `TestArbitrateFeedbackLoop`:
- `test_code_bug_feedback_reaches_generate_code_handler` — full context roundtrip
- `test_nfr8_no_scenario_vocab_in_coding_feedback` — mock LLM → assert banned terms absent in `context.feedback["generate_code"]`
- `test_scenario_error_feedback_reaches_generate_scenarios_handler`
- `test_spec_ambiguity_parks_run`

---

## Commit Boundary

**Commit**: `feat(3.28i-j): add arbiter handler, dual-pipeline orchestrator, and scenario integration pipeline`

**Files created** (~750 lines new):
- `src/specweaver/core/flow/_arbiter.py` (~220 lines)
- `src/specweaver/core/flow/_dual_pipeline.py` (~110 lines)
- `src/specweaver/workflows/pipelines/scenario_integration.yaml` (~35 lines)
- `tests/unit/core/flow/test_arbiter.py` (~130 lines)
- `tests/unit/core/flow/test_dual_pipeline.py` (~70 lines)
- `tests/unit/core/flow/test_scenario_integration_yaml.py` (~40 lines)
- `tests/unit/core/loom/test_security_readonly.py` (~55 lines)
- `tests/unit/core/loom/test_dispatcher_arbiter.py` (~40 lines)
- `tests/integration/core/flow/test_arbiter_integration.py` (~90 lines)

**Files modified** (~75 lines):
- `src/specweaver/core/loom/security.py` (+28 lines)
- `src/specweaver/core/loom/dispatcher.py` (+10 lines)
- `src/specweaver/core/loom/tools/filesystem/models.py` (+5 lines)
- `src/specweaver/core/flow/models.py` (+3 lines)
- `src/specweaver/core/flow/handlers.py` (+6 lines)
- `src/specweaver/core/flow/_decompose.py` (+5 lines)
- `src/specweaver/core/flow/_validation.py` (+7 lines)
- `tests/unit/core/flow/test_models.py` (+3 lines)

---

## Verification Plan

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

### Key assertions in verification:
- `ArbitrateVerdict` has 4 values
- `(ARBITRATE, VERDICT)` in `VALID_STEP_COMBINATIONS`
- `"arbiter_agent"` in `ROLE_INTENTS` with zero write intents
- `scenario_integration.yaml` round-trips through `PipelineDefinition`
- `ReadOnlyWorkspaceBoundary.is_read_only == True`
- `_guard_coding_feedback()` catches all 10+ scenario vocabulary terms

---

## Deviations from Design Document

| Item | Design Says | This Plan Says | Reason |
|------|------------|---------------|--------|
| `flow/_arbiter.py` module | `flow/` | `flow/_arbiter.py` | Follows naming convention of `_review.py`, `_scenario.py` |
| Stack trace filtering | "vocabulary filter" (unspecified) | `StackTraceFilterInterface` from SF-B2 | Language-aware filtering is mandatory (user requirement) |
| `WorkspaceBoundary` for arbiter | `roots=[]` | `ReadOnlyWorkspaceBoundary` subclass | Clean SRP; avoids patching existing class constructor |
