# Design: Scenario Testing — Independent Verification

- **Feature ID**: 3.28
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3.28/feature_3.28_design.md

## Feature Overview

Feature 3.28 adds independent scenario-based verification to SpecWeaver's pipeline engine, using a dual-pipeline architecture where a coding pipeline and a scenario pipeline derive tests independently from the same spec, meeting at a JOIN gate. It solves the correlated hallucination problem — where the same agent producing both code and tests creates consistently wrong but matching outputs. It leverages existing infrastructure: `GateType.JOIN` (3.27), `OrchestrateComponentsHandler` with DAG wave scheduling (3.27), `FolderGrant`/`WorkspaceBoundary` (3.26), and C09 traceability rules (3.8). Key constraints: YAML scenarios (not Gherkin), mechanical (non-LLM) pytest conversion, zero-dependency `@trace` tags for C09 compatibility.

## Research Findings

### Codebase Patterns

**Already Implemented (from prior features):**

| Component | Location | Feature | Status |
|-----------|----------|---------|--------|
| `GateType.JOIN` | `flow/models.py:60` | 3.27 | ✅ Complete |
| JOIN step stripping + Wave N deferred execution | `flow/_decompose.py:190-278` | 3.27 | ✅ Complete |
| `AsyncRateLimiterAdapter` global semaphore pool | `llm/adapters/_rate_limit.py` | 3.27 | ✅ Complete |
| `OrchestrateComponentsHandler` DAG scheduling | `flow/_decompose.py:77-291` | 3.27 | ✅ Complete |
| `FolderGrant(path, mode, recursive)` | `loom/security.py:38-49` | 3.26 | ✅ Complete |
| `AccessMode` enum (READ/WRITE/FULL) | `loom/security.py:20-26` | 3.26 | ✅ Complete |
| `WorkspaceBoundary` with `api_paths` read-only support | `loom/security.py:56-127` | 3.26 | ✅ Complete |
| `ToolDispatcher.create_standard_set(boundary, role)` | `loom/dispatcher.py:98-161` | 3.11a | ✅ Complete |
| Role-gated `FileSystemTool` with grants | `loom/tools/filesystem/tool.py` | Phase 2 | ✅ Complete |
| S07 Test-First rule (Contract section validation) | `validation/rules/spec/s07_test_first.py` | Phase 1 | ✅ Complete |
| C09 Traceability Matrix (scans `@trace` tags) | `validation/rules/code/c09_traceability.py` | 3.8 | ✅ Complete |
| `TestExpectation` model (precursor to scenarios) | `workflows/planning/models.py:133-152` | 3.6 | ✅ Complete |
| `StepHandlerRegistry` with `register()` | `flow/handlers.py:103-110` | Phase 2 | ✅ Complete |
| Pipeline runner `fan_out()` | `flow/runner.py:162-188` | 3.24 | ✅ Complete |
| `PipelineRunner` worktree sandbox execution | `flow/runner.py:287-353` | 3.26 | ✅ Complete |
| Pipeline YAML definitions (data-only) | `workflows/pipelines/*.yaml` | Phase 2 | ✅ Complete |

**Modules to Touch:**

| Module | Archetype | Change Type | context.yaml Constraint |
|--------|-----------|-------------|------------------------|
| `flow/` | orchestrator | Modify `_decompose.py` or new handler | consumes `loom/atoms`, `loom/dispatcher`, `loom/security` |
| `validation/rules/spec/` | pure-logic | Enhance S07 | No I/O, no LLM |
| `workflows/pipelines/` | data | New YAML pipeline | No code with behavior |
| `flow/models.py` | data | New StepAction + StepTarget values | No execution logic |
| `loom/dispatcher.py` | — | New `scenario_agent` role in factory | loom root can consume all sub-layers |
| `workflows/planning/` | orchestrator | New scenario generation atom adapter | consumes `llm/`, `config/` |

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| `pyyaml` | Already in `pyproject.toml` | `yaml.safe_load()` for scenario YAML parsing | Internal |
| `pytest` | Already in `pyproject.toml` | Parametrized test generation target format | Internal |
| `tree-sitter` | Already in `pyproject.toml` | AST extraction for contract generation | Internal |

### Blueprint References

- [Scenario Testing Proposal](../../scenario_testing_proposal.md) — original proposal document
- agent-system: independent verification + wave parallelism
- NVIDIA HEPH: BDD renaissance + spec-traceable scenario testing
- agentwise: agent claim verification

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
| NFR-1 | YAML scenarios, not Gherkin | LLMs produce structured data more reliably than natural-language Gherkin |
| NFR-2 | Scenario → pytest is non-LLM | Mechanical conversion eliminates a failure mode and ensures reproducibility |
| NFR-3 | Logging for all pipeline synchronization | Every JOIN wait, fan_out dispatch, and arbiter verdict must produce `logger.info` entries |
| NFR-4 | No test collision | Parallel pipelines must not share filesystem write paths; existing `FolderGrant` enforcement is sufficient |
| NFR-5 | Bounded arbiter retries | Max 3 arbiter-mediated loop-backs before HITL escalation |
| NFR-6 | Zero `@trace` tag dependency | Tags are comments (`# @trace(FR-X)`), not imports — no runtime dependency |
| NFR-7 | Backward compatibility | All existing pipeline YAML files, gate types, and handler registrations must continue to work unmodified |
| NFR-8 | Total information opacity | The coding agent MUST NOT be able to infer, discover, or be told that a second verification pipeline exists. This includes: (a) no `scenarios/` path in grants, (b) no scenario-related vocabulary in prompts or feedback, (c) arbiter feedback to the coding agent is phrased as spec-derived behavioral assertions — indistinguishable from a reviewer finding. The arbiter feedback MUST read like a review verdict, not a test failure report |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| `ruamel.yaml` | 0.18+ | `YAML(typ="safe").load()` | ✅ | Already in `pyproject.toml` |
| `pytest` | 7.0+ | `@pytest.mark.parametrize` | ✅ | Already in `pyproject.toml` |

No new external dependencies required.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Reuse `GateType.JOIN` from 3.27 directly (no new gate type) | The JOIN gate already exists and is tested in `_decompose.py`'s Wave N logic | No |
| AD-2 | Contract generation handler lives in `flow/` (new handler) | `flow/` is the orchestrator that bridges domain modules; contract extraction is a pipeline step | No |
| AD-3 | Scenario generation atom lives in `workflows/` | Matches the existing `planning/` pattern where LLM-driven generation lives | No |
| AD-4 | YAML scenario converter is a pure-logic module (no LLM) | Ensures mechanical reproducibility; lives in `workflows/` as a data transformer | No |
| AD-5 | Scenario agent role added to `ToolDispatcher.create_standard_set()` | Extends existing role-gating factory; no new security infrastructure needed | No |
| AD-6 | New `StepAction.GENERATE` + `StepTarget.CONTRACT` for contract generation | Follows existing action+target pattern; adds to `VALID_STEP_COMBINATIONS` | No |
| AD-7 | New `StepAction.GENERATE` + `StepTarget.SCENARIO` for scenario generation | Same action+target pattern as above | No |
| AD-8 | Arbiter is a new handler in `flow/` consuming `loom/dispatcher` | `flow/` already consumes `loom/dispatcher` (declared in context.yaml) | No |
| AD-9 | Arbiter agent has all-read, no-write boundary | `WorkspaceBoundary(roots=[], api_paths=[specs/, contracts/, src/, tests/, scenarios/])`. Role maps to `reviewer`-equivalent intents: `{"read_file", "list_directory", "grep", "find_files"}`. Zero write grants. The arbiter is a pure judgment agent — it reads everything, writes nothing | No |
| AD-10 | Post-JOIN flow: engine runs scenario tests, then arbiter if failures | After JOIN synchronizes both pipelines: (1) `QARunnerAtom` (engine-level, not agent-facing) executes scenario-generated pytest against coding pipeline's output. (2) If all pass → pipeline completes. (3) If any fail → `arbitrate+verdict` handler runs. (4) Arbiter produces filtered feedback → loop-back to the failing pipeline. This runs as a Wave N deferred sequence after the JOIN gate, using the existing `OrchestrateComponentsHandler` deferred-joins mechanism | No |

## Architectural Soundness — Integration Map

This section documents how every new component maps to existing infrastructure, confirming zero architectural friction.

### New Enum Values Required

| Enum | New Value | Existing Values (for context) |
|------|-----------|-------------------------------|
| `StepTarget` | `CONTRACT` | `SPEC, CODE, TESTS, FEATURE, STANDARDS, DRIFT, COMPONENTS` |
| `StepTarget` | `SCENARIO` | (same as above) |
| `StepTarget` | `VERDICT` | (same as above) — for the arbiter step |
| `StepAction` | `ARBITRATE` | `DRAFT, VALIDATE, REVIEW, GENERATE, LINT_FIX, DECOMPOSE, PLAN, ENRICH, DETECT, ORCHESTRATE` |

### New Handler Registrations

| Action + Target | Handler Class | Module | Pattern Follows |
|----------------|---------------|--------|----------------|
| `GENERATE + CONTRACT` | `GenerateContractHandler` | `flow/_generation.py` | Same as `GenerateCodeHandler` |
| `GENERATE + SCENARIO` | `GenerateScenarioHandler` | `flow/_generation.py` | Same as `GenerateTestsHandler` |
| `ARBITRATE + VERDICT` | `ArbitrateVerdictHandler` | `flow/_arbiter.py` (new) | Same as `ReviewCodeHandler` pattern |

### New ROLE_INTENTS Entry

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

### Import Legality Matrix — context.yaml Compliance

Every reused component is verified: **can the consuming module actually import it?**

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

**Result: All 12 import paths are legal.** Zero boundary violations.

### Reuse Map — What's Imported vs. Cloned vs. New

| Component | Method | Explanation |
|-----------|--------|-------------|
| `Reviewer` / `ReviewResult` / `ReviewVerdict` | **Pattern clone** | The Arbiter follows the same structure but has different verdict types (`code_bug` / `scenario_error` / `spec_ambiguity` instead of `ACCEPTED` / `DENIED`). We clone the pattern into `flow/_arbiter.py`, not import `Reviewer` directly. `flow/` CAN import from `review/` if needed for shared base types |
| `PlanSpecHandler` / `Planner` | **Pattern clone** | `GenerateScenarioHandler` follows the same handler pattern. The `ScenarioGenerator` class follows `Planner` (send structured prompt → parse structured response → save YAML). Lives in `workflows/planning/` (same module that already has `Planner`) |
| `_extract_contract()` from S06 | **Pattern clone** | Cloned into S07 as `_extract_section(spec_text, heading)`. Same module (`validation/`), no import boundary issues |
| `GenerateCodeHandler` | **Pattern clone** | `GenerateContractHandler` is the same handler structure. Lives in same file (`flow/_generation.py`) |
| `TestExpectation` model | **Import** | `flow/` consumes `planning/` → legal import. Extend or use directly as base for scenario definitions |
| `QARunnerAtom.run({"intent": "run_tests"})` | **Direct call** | `flow/` consumes `loom/atoms/qa_runner` → legal import. Used in post-JOIN Wave N to run scenario tests against code. Zero modifications to QARunnerAtom |
| `WorkspaceBoundary` + `FolderGrant` | **Direct use** | `flow/` consumes `loom/security` → legal import. Pass different constructor args for each agent boundary |
| `ToolDispatcher.create_standard_set()` | **Direct call** | `flow/` consumes `loom/dispatcher` → legal import. Pass different role + boundary args |
| `OrchestrateComponentsHandler` + Wave N | **Direct use** | Same module (`flow/`). Dual-pipeline uses existing mechanism unchanged |
| `GateType.JOIN` | **Direct use** | Same module (`flow/models.py`). Already exists |
| `ROLE_INTENTS` dict | **Additive** | Same module (`loom/tools/filesystem/models.py`). Add `"scenario_agent"` entry |
| `_extract_prompt_feedback()` | **Direct use** | Same module (`flow/_generation.py`). Arbiter writes feedback in same format → existing handlers pick it up automatically |

### Boundary Configuration per Agent

| Agent | `WorkspaceBoundary.roots` (R/W) | `api_paths` (Read-Only) | Prompt Includes |
|-------|--------------------------------|------------------------|----------------|
| Coding agent | `src/`, `tests/` | `specs/`, `contracts/` | Spec, contract, standards, constitution. **NO** scenario references of any kind |
| Scenario agent | `scenarios/` | `specs/`, `contracts/` | Spec, contract. **NO** `src/`, `tests/`, code output, stack traces |
| Arbiter agent | *(none — zero writes)* | `specs/`, `contracts/`, `src/`, `tests/`, `scenarios/` | Everything read-only. Produces structured verdict only |

### Post-JOIN Execution Flow (Critical Path)

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

## Reuse & Effort Analysis

> **Estimated new production code: ~560 lines** (vs ~2,000+ from scratch).
> The existing infrastructure handles ~70% of the work. All import paths verified legal against context.yaml boundaries.

### Per-SF Reuse Breakdown

#### SF-A: Foundation — Spec Enforcement + Contract Generation (~90 new lines)

| Component | Status | Source | Method |
|-----------|--------|--------|--------|
| `_extract_contract()` regex (S06) | 🟡 Adapt | `validation/rules/spec/s06_concrete_example.py:17-24` | Clone as `_extract_section(spec_text, heading)` — change regex from `Contract` to `Scenarios`. Same module, no boundary issues |
| S07 scoring system (`warn_score`/`fail_score`) | 🟢 Reuse | `validation/rules/spec/s07_test_first.py:55-66` | Add new check to existing `check()` method. Scoring + Finding infrastructure 100% reusable |
| Protocol/Contract section regex | 🟢 Reuse | `workflows/planning/ui_extractor.py:18-21` | `_SECTION_RE` already extracts `## Protocol` / `## Contract` sections. Production-tested regex |
| `GenerateCodeHandler` pattern | 🟢 Reuse | `flow/_generation.py:93-164` | Clone: same `_resolve_generation_routing()`, same `_extract_prompt_feedback()`, same `StepResult` with `generated_path`, same artifact UUID tracking |
| `CodeStructureAtom` (tree-sitter) | 🟡 Adapt | `loom/atoms/code_structure/atom.py` | Can extract function signatures from Contract code blocks. `flow/` consumes `loom/atoms/*` ✅ |
| YAML structure validation | 🔴 New | — | ~30 lines: parse `## Scenarios` section content, validate it's valid YAML with expected keys |
| Contract file generator | 🔴 New | — | ~60 lines: template that produces `contracts/api_contract.py` with typed Protocol class |

#### SF-B: Scenario Pipeline — Generate + Convert + Wire (~270 new lines)

| Component | Status | Source | Method |
|-----------|--------|--------|--------|
| `TestExpectation` model | 🟢 Reuse | `workflows/planning/models.py:133-152` | Already has `function_under_test`, `input_summary`, `expected_behavior`, `category: happy\|error\|boundary`. Extend with `req_id` for C09 traceability. `flow/` consumes `planning/` ✅ |
| `PlanSpecHandler` + `Planner` pattern | 🟡 Adapt | `flow/_generation.py:241-418` + `workflows/planning/planner.py` | `ScenarioGenerator` follows same pattern: structured prompt → LLM → parse structured response → validate with Pydantic → save as YAML. ~70% boilerplate reusable |
| `_extract_prompt_feedback()` | 🟢 Reuse | `flow/_generation.py:72-90` | Scenario generation handler uses identical feedback extraction for loop-back |
| C09 `@trace` tag format | 🟢 Reuse | `validation/rules/code/c09_traceability.py` | Use same `# @trace(FR-X)` comment format. C09 automatically picks up scenario-generated tags. Zero changes to C09 |
| `WorkspaceBoundary` | 🟢 Reuse | `loom/security.py:56-127` | Direct use — pass different constructor args per agent. `flow/` consumes `loom/security` ✅ |
| `FolderGrant` + `AccessMode` | 🟢 Reuse | `loom/security.py:20-49` | Direct use — different grants per agent. Same import ✅ |
| `ROLE_INTENTS` dict | 🟢 Reuse | `loom/tools/filesystem/models.py:48-78` | Add 1 entry: `"scenario_agent"`. Same module, additive only |
| `ToolDispatcher.create_standard_set()` | 🟢 Reuse | `loom/dispatcher.py:98-161` | Direct call with different args. `flow/` consumes `loom/dispatcher` ✅ |
| `OrchestrateComponentsHandler` + Wave N | 🟢 Reuse | `flow/_decompose.py:77-291` | Unchanged. Post-JOIN steps use existing deferred-joins mechanism |
| `GateType.JOIN` | 🟢 Reuse | `flow/models.py:60` | Unchanged. Already exists from 3.27 |
| Pipeline YAML | 🟢 Reuse | `workflows/pipelines/new_feature.yaml` | Clone format for `scenario_validation.yaml` |
| `ScenarioGenerator` class | 🔴 New | — | ~100 lines: LLM prompt + response parsing (but follows `Planner` pattern) |
| YAML → pytest mechanical converter | 🔴 New | — | ~150 lines: template-based conversion, parametrized pytest with `@trace` tags |
| `scenario_validation.yaml` | 🔴 New | — | ~20 lines: declarative YAML, data-only |

#### SF-C: Arbiter + Feedback Loop (~200 new lines)

| Component | Status | Source | Method |
|-----------|--------|--------|--------|
| `Reviewer` / `ReviewResult` / `ReviewVerdict` pattern | 🟡 Adapt | `workflows/review/reviewer.py:33-258` | Clone pattern for `Arbiter`: same LLM prompt → parse verdict → produce findings. Different verdict types. `flow/` consumes `review/` ✅ |
| `PromptBuilder` | 🟢 Reuse | `infrastructure/llm/prompt_builder.py` | Direct import for assembling arbiter context. `flow/` consumes `llm/` ✅ |
| `QARunnerAtom._intent_run_tests()` | 🟢 Reuse | `loom/atoms/qa_runner/atom.py:104-155` | Direct call: `QARunnerAtom.run({"intent": "run_tests", "target": "scenarios/generated/"})`. Zero modifications. `flow/` consumes `loom/atoms/qa_runner` ✅ |
| `_extract_prompt_feedback()` | 🟢 Reuse | `flow/_generation.py:72-90` | Arbiter writes filtered verdict into `context.feedback` using same format → existing coding/scenario handlers automatically consume it on loop-back |
| `ArbitrateVerdictHandler` | 🔴 New | — | ~120 lines: new handler in `flow/_arbiter.py` (follows `ReviewCodeHandler` pattern) |
| Feedback vocabulary filter (NFR-8) | 🔴 New | — | ~80 lines: strips scenario vocabulary from coding agent feedback, rephrases as spec-derived behavioral assertions |

### Summary

| Category | Count | % of Total |
|----------|-------|-----------|
| 🟢 Direct reuse (zero changes) | 9 components | ~50% of overall effort |
| 🟡 Adapt (minor modifications) | 4 components | ~20% of overall effort |
| 🔴 New code (truly new) | 3 core components | ~30% of overall effort |

**No existing code needs breaking changes.** All modifications are additive:
- S07: new check added to existing `check()` method
- `ROLE_INTENTS`: new dict entry
- `StepAction` / `StepTarget`: new enum values
- `VALID_STEP_COMBINATIONS`: new tuples added to frozenset
- `StepHandlerRegistry.__init__()`: 3 new handler entries
- `handlers.py`: 3 new imports + `__all__` entries

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Scenario Testing Guide | How to add scenario inputs to specs, how the dual-pipeline works, how to interpret arbiter feedback | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

> **Consolidation (5→3)**: Original 11 sub-features (3.28a–j) were first consolidated to 5, then to 3 balanced SFs after identifying that SF-4 was too thin (~20 lines) for its own commit boundary, and SF-1/SF-2 were both small independent foundation work.
>
> **Key reuse insight**: 3.28g (JOIN gate) and 3.28h (parallel orchestrator) are **already fully implemented** by Feature 3.27. The `scenario_agent` role (3.28e) is ~60% done — only a new role definition in the dispatcher factory is needed.

### SF-A: Foundation — Spec Enforcement + Contract Generation (3.28a + 3.28b)
- **Scope**: Enhance S07 validation rule to require a `## Scenarios` section with structured YAML. New pipeline handler that extracts Python Protocol/ABC from a spec's `## Contract` section.
- **FRs**: [FR-1, FR-2]
- **Inputs**: Spec markdown text, validated spec with `## Contract` section
- **Outputs**: S07 finding if `## Scenarios` section is missing or malformed. `contracts/api_contract.py` containing typed Protocol class.
- **Reuse**: Clone S06's `_extract_contract()` regex → `_extract_section()`. Reuse S07's scoring. Clone `GenerateCodeHandler` pattern. `ui_extractor.py` Contract regex. `CodeStructureAtom` for signature extraction.
- **New code**: ~90 lines (YAML validation ~30 + contract file generator ~60)
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3.28/feature_3.28_sfa_implementation_plan.md

### SF-B: Scenario Pipeline — Generate + Convert + Wire (3.28c + 3.28d + 3.28e + 3.28f + 3.28g + 3.28h)
- **Scope**: LLM-driven scenario generation from spec + API contract → structured YAML. Mechanical YAML → pytest conversion with `@trace` tags. Add `scenario_agent` role to dispatcher. Enforce **total information opacity** for the coding agent (FR-5b). Create `scenario_validation.yaml` pipeline. Wire dual-pipeline parallel execution. **Note**: 3.28g (JOIN gate) and 3.28h (parallel orchestrator) are already complete from 3.27.
- **FRs**: [FR-3, FR-4, FR-5a, FR-5b, FR-6, FR-7]
- **Inputs**: Spec content, API contract (Protocol class), `req_id` list from spec
- **Outputs**: `scenarios/definitions/*.yaml` + `scenarios/generated/*.py` (parametrized pytest). Two fully isolated parallel pipelines with JOIN synchronization. Coding agent has zero awareness of scenario pipeline.
- **Reuse**: `TestExpectation` model (extend with `req_id`), `Planner` pattern, `_extract_prompt_feedback()`, C09 `@trace` format, all security infrastructure (WorkspaceBoundary, FolderGrant, AccessMode, ROLE_INTENTS, ToolDispatcher, OrchestrateComponentsHandler, GateType.JOIN).
- **New code**: ~270 lines (ScenarioGenerator ~100 + YAML→pytest converter ~150 + pipeline YAML ~20)
- **Depends on**: SF-A
- **Impl Plan**: docs/roadmap/phase_3/feature_3.28/feature_3.28_sfb_implementation_plan.md

### SF-C: Arbiter + Feedback Loop (3.28i + 3.28j)
- **Scope**: Arbiter agent for error attribution on scenario test failures. Runs post-JOIN after `QARunnerAtom` executes scenario tests against code. The arbiter has **all-read, no-write** boundary (`api_paths` only, zero `roots`). Produces filtered feedback that preserves total information opacity — coding agent feedback reads like a reviewer finding (AD-9, AD-10). HITL escalation on spec ambiguity.
- **FRs**: [FR-8, FR-9, FR-10]
- **Inputs**: Scenario test results (pass/fail from QARunnerAtom), spec content, API contract, coding pipeline's `src/` output, scenario pipeline's `scenarios/` output
- **Outputs**: Filtered feedback reports (one per pipeline, vocabulary-filtered per NFR-8), or HITL escalation. Coding agent feedback contains NO scenario vocabulary — phrased as "Spec clause §X requires Y. Your implementation does Z."
- **Reuse**: `Reviewer`/`ReviewResult` pattern, `PromptBuilder`, `QARunnerAtom._intent_run_tests()` (zero modifications), `_extract_prompt_feedback()` for loop-back mechanism.
- **New code**: ~200 lines (ArbitrateVerdictHandler ~120 + vocabulary filter ~80)
- **Depends on**: SF-B
- **Impl Plan**: docs/roadmap/phase_3/feature_3.28/feature_3.28_sfc_implementation_plan.md

## Execution Order

```
SF-A (Foundation) ──── SF-B (Scenario Pipeline) ──── SF-C (Arbiter)
   ~90 lines              ~270 lines                   ~200 lines
```

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-A | Foundation: Spec Enforcement + Contract Generation | — | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| SF-B | Scenario Pipeline: Generate + Convert + Wire | SF-A | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-C | Arbiter + Feedback Loop | SF-B | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-A dev COMPLETE (pending pre-commit + commit). SF-B implementation plan in progress.
**Next step**: Run `/implementation-plan docs/roadmap/phase_3/feature_3.28/feature_3.28_design.md sf-b`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
