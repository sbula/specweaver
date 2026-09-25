# B-FLOW-01 — Scenario Testing: Independent Verification

**Status**: APPROVED. SF-A, SF-B, SF-C committed; SF-B2 (polyglot) implemented. · **Feature ID**:
3.28 · **Phase**: 3

| | |
|---|---|
| Builds on | `GateType.JOIN` + `OrchestrateComponentsHandler` DAG wave scheduling (3.27) · `FolderGrant` / `WorkspaceBoundary` (3.26) · C09 traceability rules (3.8) |
| Extends | S07 Test-First rule · `ROLE_INTENTS` · `StepAction` / `StepTarget` |
| Blueprints | [Scenario Testing Proposal](../../scenario_testing_proposal.md) — original proposal · agent-system: independent verification + wave parallelism · NVIDIA HEPH: BDD renaissance + spec-traceable scenario testing · agentwise: agent claim verification |
| Guide | Scenario Testing Guide — `docs/dev_guides/scenario_pipelines.md` |

## What it does

Two pipelines derive tests from the same spec, independently, and meet at a JOIN gate:

- the **coding pipeline** writes code and its own tests;
- the **scenario pipeline** writes YAML scenarios and converts them mechanically to tests.

After the JOIN, the engine runs the scenario tests against the code. On failure an **arbiter**
decides who is at fault — code, scenario, or spec — and routes filtered feedback back.

## Why

When one agent writes both code and tests, both can be wrong in the same way and still agree —
correlated hallucination. Independent derivation from the spec breaks that link. The coding agent
must never learn the scenario pipeline exists, or it can write to the test instead of the spec.

Constraints: YAML scenarios (not Gherkin); mechanical (non-LLM) pytest conversion; zero-dependency
`@trace` tags for C09 compatibility.

## Architecture

```
                    ┌── Coding Pipeline ──────┐
                    │  spec → plan → code     │
    Spec ──→ API ──→│  → tests → validate     │──→ JOIN ──→ Run Scenario ──→ All Pass? ──→ DONE
    Contract        │                         │    Gate     Tests vs Code      │
                    ├── Scenario Pipeline ────┤                                │
                    │  spec → scenarios →     │                            FAIL
                    │  YAML → pytest          │                                │
                    └─────────────────────────┘                                ▼
                                                                          Arbiter
                                                                             │
                                                            ┌────────────────┼────────────────┐
                                                        code_bug       scenario_error     spec_ambiguity
                                                            │                │                  │
                                                        Feedback to       Feedback to       HITL
                                                        coding agent      scenario agent    Escalation
                                                        (as review        (as spec-delta
                                                         finding)          report)
                                                            │                │
                                                        Loop-back to     Loop-back to
                                                        coding pipeline  scenario pipeline
```

### Modules touched

| Module | Archetype | Change Type | context.yaml Constraint |
|--------|-----------|-------------|------------------------|
| `flow/` | orchestrator | Modify `_decompose.py` or new handler | consumes `loom/atoms`, `loom/dispatcher`, `loom/security` |
| `validation/rules/spec/` | pure-logic | Enhance S07 | No I/O, no LLM |
| `workflows/pipelines/` | data | New YAML pipeline | No code with behavior |
| `flow/models.py` | data | New StepAction + StepTarget values | No execution logic |
| `loom/dispatcher.py` | — | New `scenario_agent` role in factory | loom root can consume all sub-layers |
| `workflows/planning/` | orchestrator | New scenario generation atom adapter | consumes `llm/`, `config/` |

Reused as is (locations and line refs in the [SF-A plan](B-FLOW-01_sfa_implementation_plan.md)):
the JOIN gate and Wave N deferred execution, `AsyncRateLimiterAdapter`, `FolderGrant` /
`AccessMode` / `WorkspaceBoundary`, `ToolDispatcher.create_standard_set(boundary, role)`, role-gated
`FileSystemTool`, S07, C09, `TestExpectation`, `StepHandlerRegistry`, `fan_out()`, the
`PipelineRunner` worktree sandbox, and the data-only pipeline YAMLs.

### New enum values

| Enum | New Value | Existing Values (for context) |
|------|-----------|-------------------------------|
| `StepTarget` | `CONTRACT` | `SPEC, CODE, TESTS, FEATURE, STANDARDS, DRIFT, COMPONENTS` |
| `StepTarget` | `SCENARIO` | (same as above) |
| `StepTarget` | `VERDICT` | (same as above) — for the arbiter step |
| `StepAction` | `ARBITRATE` | `DRAFT, VALIDATE, REVIEW, GENERATE, LINT_FIX, DECOMPOSE, PLAN, ENRICH, DETECT, ORCHESTRATE` |

### New handler registrations

| Action + Target | Handler Class | Module | Pattern Follows |
|----------------|---------------|--------|----------------|
| `GENERATE + CONTRACT` | `GenerateContractHandler` | `flow/_generation.py` | Same as `GenerateCodeHandler` |
| `GENERATE + SCENARIO` | `GenerateScenarioHandler` | `flow/_generation.py` | Same as `GenerateTestsHandler` |
| `ARBITRATE + VERDICT` | `ArbitrateVerdictHandler` | `flow/_arbiter.py` (new) | Same as `ReviewCodeHandler` pattern |

### New `ROLE_INTENTS` entry

```python
# In loom/tools/filesystem/models.py — ROLE_INTENTS dict
"scenario_agent": frozenset({
    "read_file",      # Read specs, contracts, own scenarios
    "write_file",     # Write scenario definitions
    "create_file",    # Create new scenario files
    "list_directory", # Browse scenarios/ dir
    "grep",           # Search within granted paths only
    "find_files",     # Find files within granted paths only
}),
```

### Boundary per agent

| Agent | `WorkspaceBoundary.roots` (R/W) | `api_paths` (Read-Only) | Prompt Includes |
|-------|--------------------------------|------------------------|----------------|
| Coding agent | `src/`, `tests/` | `specs/`, `contracts/` | Spec, contract, standards, constitution. **NO** scenario references of any kind |
| Scenario agent | `scenarios/` | `specs/`, `contracts/` | Spec, contract. **NO** `src/`, `tests/`, code output, stack traces |
| Arbiter agent | *(none — zero writes)* | `specs/`, `contracts/`, `src/`, `tests/`, `scenarios/` | Everything read-only. Produces structured verdict only |

### Import legality (context.yaml)

Every reused component was checked: can the consuming module import it? All 12 import paths are
legal; zero boundary violations.

| Consumer Module | Reused Component | Source Module | Consumer `consumes` | Source `forbids` | Legal? | Type |
|----------------|-----------------|---------------|---------------------|-----------------|--------|------|
| `flow/` | `Reviewer`, `ReviewResult` | `review/` | ✅ `consumes: specweaver/review` | `forbids: specweaver/loom/*` (N/A) | ✅ **Legal** | Import |
| `flow/` | `Planner`, `PlanArtifact` | `planning/` | ✅ `consumes: specweaver/planning` | `forbids: specweaver/loom/*` (N/A) | ✅ **Legal** | Import |
| `flow/` | `Generator` | `implementation/` | ✅ `consumes: specweaver/implementation` | `forbids: []` | ✅ **Legal** | Import |
| `flow/` | `QARunnerAtom` | `loom/atoms/qa_runner/` | ✅ `consumes: specweaver/loom/atoms/qa_runner` | `forbids: specweaver/loom/tools/*` (N/A) | ✅ **Legal** | Import |
| `flow/` | `WorkspaceBoundary`, `FolderGrant`, `AccessMode` | `loom/security` | ✅ `consumes: specweaver/loom/security` | — | ✅ **Legal** | Import |
| `flow/` | `ToolDispatcher.create_standard_set()` | `loom/dispatcher` | ✅ `consumes: specweaver/loom/dispatcher` | — | ✅ **Legal** | Import |
| `flow/` | `_extract_prompt_feedback()` | `flow/` (self) | ✅ Same module | — | ✅ **Legal** | Internal |
| `flow/` | `GenerateCodeHandler` pattern | `flow/` (self) | ✅ Same module | — | ✅ **Legal** | Clone |
| `validation/` (S07) | `_extract_contract()` pattern from S06 | `validation/` (self) | ✅ Same module | — | ✅ **Legal** | Clone |
| `flow/_arbiter.py` | `ReviewVerdict` pattern from `review/` | `review/` | ✅ `flow/` consumes `review/` | — | ✅ **Legal** | Import |
| `flow/_arbiter.py` | `PromptBuilder` | `llm/` | ✅ `flow/` consumes `specweaver/llm` | — | ✅ **Legal** | Import |
| `loom/tools/filesystem/models.py` | N/A — additive dict entry | `loom/tools/` (self) | ✅ Same module | — | ✅ **Legal** | Internal |

### Reuse map — imported, cloned, new

| Component | Method | Explanation |
|-----------|--------|-------------|
| `Reviewer` / `ReviewResult` / `ReviewVerdict` | **Pattern clone** | The Arbiter has the same structure but different verdict types (`code_bug` / `scenario_error` / `spec_ambiguity` instead of `ACCEPTED` / `DENIED`). Cloned into `flow/_arbiter.py`, not importing `Reviewer`. `flow/` CAN import from `review/` for shared base types |
| `PlanSpecHandler` / `Planner` | **Pattern clone** | `GenerateScenarioHandler` follows the same handler pattern. `ScenarioGenerator` follows `Planner` (structured prompt → parse structured response → save YAML). Lives in `workflows/planning/` (same module as `Planner`) |
| `_extract_contract()` from S06 | **Pattern clone** | Cloned into S07 as `_extract_section(spec_text, heading)`. Same module (`validation/`) |
| `GenerateCodeHandler` | **Pattern clone** | `GenerateContractHandler` has the same handler structure, in the same file (`flow/_generation.py`) |
| `TestExpectation` model | **Import** | `flow/` consumes `planning/`. Extend or use directly as base for scenario definitions |
| `QARunnerAtom.run({"intent": "run_tests"})` | **Direct call** | `flow/` consumes `loom/atoms/qa_runner`. Runs scenario tests against code in post-JOIN Wave N. Zero modifications to QARunnerAtom |
| `WorkspaceBoundary` + `FolderGrant` | **Direct use** | `flow/` consumes `loom/security`. Different constructor args per agent boundary |
| `ToolDispatcher.create_standard_set()` | **Direct call** | `flow/` consumes `loom/dispatcher`. Different role + boundary args |
| `OrchestrateComponentsHandler` + Wave N | **Direct use** | Same module (`flow/`). Dual-pipeline uses the existing mechanism unchanged |
| `GateType.JOIN` | **Direct use** | Same module (`flow/models.py`). Already exists |
| `ROLE_INTENTS` dict | **Additive** | Same module (`loom/tools/filesystem/models.py`). Add `"scenario_agent"` entry |
| `_extract_prompt_feedback()` | **Direct use** | Same module (`flow/_generation.py`). The arbiter writes feedback in the same format, so existing handlers pick it up |

No existing code needs breaking changes. All modifications are additive:
- S07: new check added to existing `check()` method
- `ROLE_INTENTS`: new dict entry
- `StepAction` / `StepTarget`: new enum values
- `VALID_STEP_COMBINATIONS`: new tuples added to frozenset
- `StepHandlerRegistry.__init__()`: 3 new handler entries
- `handlers.py`: 3 new imports + `__all__` entries

### External dependencies

No new external dependencies.

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| `ruamel.yaml` | 0.18+ | `YAML(typ="safe").load()` — scenario YAML parsing | ✅ | Already in `pyproject.toml` |
| `pytest` | 7.0+ | `@pytest.mark.parametrize` — generated test format | ✅ | Already in `pyproject.toml` |
| `tree-sitter` | — | AST extraction for contract generation | ✅ | Already in `pyproject.toml` |

`pyyaml` (`pyyaml 6.0+`, `yaml.safe_load()`) was listed at first; the project uses `ruamel.yaml`.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Reuse `GateType.JOIN` from 3.27 directly (no new gate type) | The JOIN gate already exists and is tested in `_decompose.py`'s Wave N logic | No |
| AD-2 | Contract generation handler lives in `flow/` (new handler) | `flow/` is the orchestrator that bridges domain modules; contract extraction is a pipeline step | No |
| AD-3 | Scenario generation atom lives in `workflows/` | Matches the existing `planning/` pattern where LLM-driven generation lives | No |
| AD-4 | YAML scenario converter is a pure-logic module (no LLM) | Mechanical reproducibility; lives in `workflows/` as a data transformer | No |
| AD-5 | Scenario agent role added to `ToolDispatcher.create_standard_set()` | Extends the existing role-gating factory; no new security infrastructure | No |
| AD-6 | New `StepAction.GENERATE` + `StepTarget.CONTRACT` for contract generation | Follows the existing action+target pattern; adds to `VALID_STEP_COMBINATIONS` | No |
| AD-7 | New `StepAction.GENERATE` + `StepTarget.SCENARIO` for scenario generation | Same action+target pattern as above | No |
| AD-8 | Arbiter is a new handler in `flow/` consuming `loom/dispatcher` | `flow/` already consumes `loom/dispatcher` (declared in context.yaml) | No |
| AD-9 | Arbiter agent has all-read, no-write boundary | `WorkspaceBoundary(roots=[], api_paths=[specs/, contracts/, src/, tests/, scenarios/])`. Role maps to `reviewer`-equivalent intents: `{"read_file", "list_directory", "grep", "find_files"}`. Zero write grants. The arbiter is a pure judgment agent — it reads everything, writes nothing | No |
| AD-10 | Post-JOIN flow: engine runs scenario tests, then arbiter if failures | After JOIN synchronizes both pipelines: (1) `QARunnerAtom` (engine-level, not agent-facing) executes scenario-generated pytest against coding pipeline's output. (2) If all pass → pipeline completes. (3) If any fail → `arbitrate+verdict` handler runs. (4) Arbiter produces filtered feedback → loop-back to the failing pipeline. This runs as a Wave N deferred sequence after the JOIN gate, using the existing `OrchestrateComponentsHandler` deferred-joins mechanism | No |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Spec template enforcement | Validation engine | Verify that component specs contain a `## Scenarios` section with structured YAML inputs | S07 rejects specs without scenario inputs; findings include line numbers and severity |
| FR-2 | API contract generation | Pipeline handler | Extract Python Protocol/ABC from a spec's `## Contract` section | Produces `contracts/api_contract.py` with typed method signatures and docstrings |
| FR-3 | Scenario generation (LLM) | Scenario generation atom | Generate structured YAML scenarios from spec + API contract | Produces ≥1 scenario per public method covering happy, error, and boundary paths. Each scenario maps to a `req_id` from the spec |
| FR-4 | Scenario → pytest conversion | Mechanical converter | Transform YAML scenarios into parametrized pytest files | Produces executable pytest files with `# @trace(FR-X)` tags for C09. Zero LLM involvement |
| FR-5a | Scenario agent isolation | Loom security layer | Restrict the scenario agent's filesystem access to `specs/` (read-only) + `contracts/` (read-only) + `scenarios/` (read-write) only | Agent cannot read `src/` or `tests/`; `FolderGrant` enforcement blocks all unauthorized I/O |
| FR-5b | Coding agent isolation | Loom security layer + PromptBuilder + RunContext | The coding agent MUST have zero awareness of the scenario pipeline — no `scenarios/` filesystem grant, no scenario references in its system prompt, no scenario pipeline status in its `RunContext`, no mention of scenarios in error messages or feedback | From the coding agent's perspective, the scenario pipeline does not exist. Total information opacity |
| FR-6 | Scenario validation pipeline | Pipeline YAML | Define `scenario_validation.yaml` with steps: generate_contract → generate_scenarios → convert_to_pytest → signal READY | Pipeline executes end-to-end and produces a `READY` signal upon completion |
| FR-7 | Dual-pipeline parallel execution | OrchestrateComponentsHandler | Run coding pipeline and scenario pipeline in parallel, synchronize at JOIN gate | Both pipelines complete independently; JOIN gate blocks until both signal READY |
| FR-8 | Arbiter error attribution | Arbiter agent | On scenario test failure, determine fault: code bug / scenario error / spec ambiguity | Arbiter produces exactly two filtered feedback reports: one for coding agent (no scenario details whatsoever), one for scenario agent (no implementation code) |
| FR-9 | Filtered feedback loop (one-way opacity) | Pipeline engine | Route arbiter verdicts to the correct pipeline with context filtered to preserve total isolation | Coding agent receives ONLY: spec clause reference + behavioral expectation ("function X MUST do Y") + its own stack trace. It does NOT receive: scenario YAML, scenario test file names, scenario test output, scenario pipeline existence, or the word "scenario" in any form. Scenario agent receives ONLY: spec clause reference + expected-vs-actual behavioral delta. It does NOT receive: source code, file paths in `src/`, implementation details |
| FR-10 | HITL escalation on spec ambiguity | Arbiter agent | When arbiter determines spec ambiguity, escalate to human | HITL gate presents both interpretations and asks the human to clarify |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | YAML scenarios, not Gherkin | LLMs produce structured data more reliably than natural-language Gherkin **[proof: none — unfalsifiable as written]** |
| NFR-2 | Scenario → pytest is non-LLM | Mechanical conversion eliminates a failure mode and ensures reproducibility |
| NFR-3 | Logging for all pipeline synchronization | Every JOIN wait, fan_out dispatch, and arbiter verdict must produce `logger.info` entries |
| NFR-4 | No test collision | Parallel pipelines must not share filesystem write paths; existing `FolderGrant` enforcement is sufficient |
| NFR-5 | Bounded arbiter retries | Max 3 arbiter-mediated loop-backs before HITL escalation |
| NFR-6 | Zero `@trace` tag dependency | Tags are comments (`# @trace(FR-X)`), not imports — no runtime dependency |
| NFR-7 | Backward compatibility | All existing pipeline YAML files, gate types, and handler registrations must continue to work unmodified |
| NFR-8 | Total information opacity | The coding agent MUST NOT be able to infer, discover, or be told that a second verification pipeline exists. This includes: (a) no `scenarios/` path in grants, (b) no scenario-related vocabulary in prompts or feedback, (c) arbiter feedback to the coding agent is phrased as spec-derived behavioral assertions — indistinguishable from a reviewer finding. The arbiter feedback MUST read like a review verdict, not a test failure report **[proof: none — unfalsifiable as written]** |

## Sub-features

The original 11 sub-features (3.28a–j) were merged into three. 3.28g (JOIN gate) and 3.28h
(parallel orchestrator) were already implemented by 3.27.

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-A (3.28a + 3.28b) | S07 requires a `## Scenarios` section with structured YAML; new handler extracts a Python Protocol/ABC from the spec's `## Contract`. | FR-1, FR-2 | spec markdown with `## Contract` → S07 finding if `## Scenarios` is missing or malformed; `contracts/api_contract.py` with a typed Protocol class | none | [sfa](B-FLOW-01_sfa_implementation_plan.md) |
| SF-B (3.28c + 3.28d + 3.28e + 3.28f + 3.28g + 3.28h) | LLM scenario generation from spec + API contract → YAML; mechanical YAML → pytest with `@trace` tags; `scenario_agent` role; **total information opacity** for the coding agent (FR-5b); `scenario_validation.yaml`; dual-pipeline wiring. | FR-3, FR-4, FR-5a, FR-5b, FR-6, FR-7 | spec, API contract (Protocol class), `req_id` list → `scenarios/definitions/*.yaml` + `scenarios/generated/*.py` (parametrized pytest); two isolated parallel pipelines with JOIN; coding agent unaware of the scenario pipeline | SF-A | [sfb](B-FLOW-01_sfb_implementation_plan.md) |
| SF-B2 | Polyglot scenario pipeline: converters, contract renderers and stack-trace filters for Python, Java, Kotlin, TypeScript, Rust. | FR-4 (NFR-1, NFR-2) | — | SF-B | [sfb2](B-FLOW-01_sfb2_implementation_plan.md) |
| SF-C (3.28i + 3.28j) | Arbiter for error attribution, run post-JOIN after `QARunnerAtom` executes scenario tests. **All-read, no-write** boundary (`api_paths` only, zero `roots`). Filtered feedback keeps total information opacity — coding feedback reads like a reviewer finding (AD-9, AD-10). HITL escalation on spec ambiguity. | FR-8, FR-9, FR-10 | scenario test results (pass/fail from QARunnerAtom), spec, API contract, `src/` output, `scenarios/` output → one filtered feedback report per pipeline (vocabulary-filtered per NFR-8), or HITL escalation. Coding feedback has NO scenario vocabulary — phrased as "Spec clause §X requires Y. Your implementation does Z." | SF-B, SF-B2 | [sfc](B-FLOW-01_sfc_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-A | Foundation: Spec Enforcement + Contract Generation | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-B | Scenario Pipeline: Generate + Convert + Wire | SF-A | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-C | Arbiter + Feedback Loop | SF-B | ✅ | ✅ | ✅ | ✅ | ✅ |
