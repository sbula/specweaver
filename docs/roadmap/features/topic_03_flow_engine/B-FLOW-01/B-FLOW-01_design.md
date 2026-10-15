# B-FLOW-01 — Scenario Testing: Independent Verification

**Status**: 🔧 REOPENED 2026-10-15 — repair design APPROVED by the user 2026-10-15. SF-A, SF-B, SF-B2, SF-C committed;
the repair adds SF-D..SF-H. Findings: [b_flow_01_isolation_2026-10-15.md](../../../analysis/b_flow_01_isolation_2026-10-15.md). · **Feature ID**:
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
    "list_directory",
    "grep",
    "find_files",
}),
```

The scenario agent reads, and never writes: it returns its scenarios and the pipeline writes the
file. This replaces the 2026-10-12 decision to give it `write_file` and `create_file`
`[agreed 2026-10-15]`.

### Boundary per agent

| Agent | `WorkspaceBoundary.roots` (R/W) | `api_paths` (Read-Only) | Prompt Includes |
|-------|--------------------------------|------------------------|----------------|
| Coding agent | the project root; scenario files are not in it (FR-11) | `specs/`, `contracts/` | Spec, contract, standards, constitution. **NO** scenario references of any kind |
| Scenario agent | *(none — reads only)* | `specs/`, `contracts/`, its scenario store | Spec, contract. **NO** `src/`, `tests/`, code output, stack traces |
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
| AD-11 | Scenario files live outside the project, in SpecWeaver's data directory; the coder's and the scenario tests run in a container | grants guard tools, not running code or git: only absence from the project closes every path `[agreed 2026-10-15]`. This replaces the earlier "grants leave out `scenarios/`" choice, which nothing then needs | **Yes** — a new store outside the project, and containers required for dual runs |
| AD-12 | `B-INTL-07` (Error Attribution Arbiter) retired into this feature | SF-C built it (`core/flow/handlers/arbiter.py`); one arbiter, one owner `[agreed 2026-10-15]` | No |
| AD-13 | The arbiter stays one model's verdict; execution voting (several code samples, re-derived expectations) is not built | a wrong verdict is bounded by isolation: a wrong "scenario error" only makes the scenario side regenerate from the spec, blind to the code `[agreed 2026-10-15]` | No |
| AD-14 | Scenario tests are the acceptance layer; the coder's tests stay its working tests; overlap is reported per requirement (FR-13), never removed | two independent tests agreeing is the evidence this feature exists for `[agreed 2026-10-15]` | No |
| AD-10 | Post-JOIN flow: engine runs scenario tests, then arbiter if failures | After JOIN synchronizes both pipelines: (1) `QARunnerAtom` (engine-level, not agent-facing) executes scenario-generated pytest against coding pipeline's output. (2) If all pass → pipeline completes. (3) If any fail → `arbitrate+verdict` handler runs. (4) Arbiter produces filtered feedback → loop-back to the failing pipeline. This runs as a Wave N deferred sequence after the JOIN gate, using the existing `OrchestrateComponentsHandler` deferred-joins mechanism | No |

## Functional Requirements

FR-1, FR-4, FR-9 and FR-10 are unchanged. FR-2, 3, 5a, 5b, 6, 7 and 8 were rewritten 2026-10-15 to
what holds, or what the repair builds `[agreed 2026-10-15]`. FR-11..FR-21 are the repair. A **seam**
FR needs a capability outside this one.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Scenario hints checked | Validation engine | SHALL accept a spec without `## Scenarios`, and SHALL fail S07 on a `## Scenarios` section with no YAML block or YAML that cannot be read, and warn on a scenario that misses a key, each finding naming the section's line and a severity `[agreed 2026-10-13]` | the section stays optional hints for scenario generation, and a broken one is caught |
| FR-2 | API contract generation | Pipeline handler | SHALL extract the contract from a spec's `## Contract` in the project's language — a Python Protocol, a Java, Kotlin or TypeScript interface, a Rust trait — naming each method `Class.method` | `contracts/<stem>_contract.<ext>` with the typed signatures and docstrings of the spec |
| FR-3 | Scenario generation | Scenario generator | SHALL generate YAML scenarios from the spec and the contract, each naming its method `Class.method` as the contract declares it, and SHALL refuse a result with no scenario, a `req_id` the spec does not declare, a method the contract does not declare, or a contract method no scenario calls | every contract method is checked, and every scenario traces to a real requirement |
| FR-4 | Scenario → pytest conversion | Mechanical converter | Transform YAML scenarios into parametrized pytest files | Produces executable pytest files with `# @trace(FR-X)` tags for C09. Zero LLM involvement |
| FR-5a | Scenario agent tools | Tool dispatcher | SHALL give the scenario agent the file tools only — read, list, search; no write, git, code-structure or web tool — READ on `specs/` and `contracts/`; its earlier set for the spec comes in its prompt, because the store is outside the project `[agreed 2026-10-15]`; it MAY report a contract or spec problem, which is shown to the person at the end of the run and never goes into the contract `[agreed 2026-10-15]` | the agent sees every contract it tests against, and its only output is the scenario set the pipeline stores |
| FR-5b | Coder sees nothing of the scenario side | Prompt builder, run context | SHALL give each side of a dual run its own `feedback`, and SHALL keep every scenario-side word, path and value out of the coder's prompt and feedback; the person's `## Scenarios` hints stay in the coder's copy of the spec `[agreed 2026-10-15]` | the coder's inputs are the spec, the contract and its own results — nothing the scenario side made |
| FR-6 | Scenario pipeline | Pipeline YAML | `scenario_validation.yaml` SHALL run `generate_scenarios` then `convert_to_pytest`; the contract is generated once, before the two sides start (`scenario_integration.yaml`) | both sides read one contract |
| FR-7 | Parallel sides, joined | Dual-pipeline handler | SHALL run the coding and the scenario side at the same time and continue only when both ended | the two runs overlap in time, and the scenario tests run only after both ended |
| FR-8 | Arbiter attribution | Arbiter | On a failed scenario test SHALL give one verdict — code bug, scenario error, or spec ambiguity — and send one report to the side at fault `[agreed 2026-10-15]` | the side at fault learns what to fix, and nothing crosses to the other side |
| FR-9 | Filtered feedback loop (one-way opacity, both ways) | Pipeline engine | Route arbiter verdicts to the side at fault with context filtered to preserve isolation | Coding side receives ONLY: spec clause reference + behavioral expectation ("function X MUST do Y") + its own stack trace (the frames of its code and their error; none when the failure is an assertion in the check). It does NOT receive: scenario YAML, scenario test file names, scenario test output, scenario pipeline existence, or the word "scenario" in any form. Scenario side receives ONLY: spec clause reference + the disputed expectation + the arbiter's reason; never source code, a path in the project, or any value the code produced `[agreed 2026-10-15]` |
| FR-10 | HITL escalation on spec ambiguity | Arbiter agent | When arbiter determines spec ambiguity, SHALL park naming the clause, its readings and the spec file; the person settles it by editing the spec `[agreed 2026-10-13]` | resumed with the spec unchanged, the run parks again with no model call; with it edited, the round runs again |
| FR-11 | Scenario files outside the project | Scenario store (SpecWeaver data directory) | Scenario sets and their tests SHALL be stored outside the project, in SpecWeaver's own data directory per project — never in the repository, never in git `[agreed 2026-10-15]` | no tool, search, git command, mention or running code inside the project can reach them |
| FR-12 | Seam: memory stays on its side | Run memory (`D-INTL-06`) | A scenario-side or arbiter text SHALL never enter memory a coder prompt reads, and a coder-side text SHALL never enter memory the scenario side reads `[agreed 2026-10-15]` | neither side learns the other's past through memory |
| FR-13 | Seam: coverage counted apart | C09 (`C-VAL-04`) | The coder's C09 SHALL count only the coder's tests; per requirement the run SHALL report to the person whether both sides, the coder only, or the scenario side only cover it `[agreed 2026-10-15]` | a gap in the coder's tests is no longer hidden by a scenario test |
| FR-14 | Scenario tests run apart | Scenario test step, container | The scenario tests SHALL run in a container that mounts the project and the scenario store read-only, placing each test where its language's build needs it inside the container only; the project tree never holds a scenario test `[agreed 2026-10-15]` | a scenario run leaves nothing in the project, also when it crashes |
| FR-15 | One spec for both sides | Dual-pipeline handler, spec review | Spec review SHALL record the reviewed spec's fingerprint; a dual run SHALL start only when the spec matches it, SHALL check it again before arbitrating, and its coding side SHALL skip drafting and reviewing the spec `[agreed 2026-10-15]` | both sides read the same reviewed spec, unchanged during the run |
| FR-16 | Only the side at fault runs again | Arbiter loop | After a verdict SHALL run again only the side at fault, keeping the other side's output; each side has its own feedback outbox, handed only to that side `[agreed 2026-10-15]` | fixed scenarios stay a stable target, and each round costs one side |
| FR-17 | Different models | Dual-pipeline handler | When the roles in `settings.toml` name two or more distinct models and the resolved models of the `generate_code` and `generate_scenarios` roles are the same, the dual run SHALL refuse, naming the two settings keys; with one model it SHALL warn and say so in the run report; `--model` sets the coding side only, the one exception to `C-FLOW-13` FR-3 `[agreed 2026-10-15]` | the two sides do not share one model's misreadings where the settings allow otherwise |
| FR-18 | Fail closed | Dual-pipeline handler | A dual run SHALL refuse to start, naming why, when no container can run the coder's and the scenario tests, or when FR-5b or FR-11 cannot hold `[agreed 2026-10-15]` | a dual run that only looks independent never runs |
| FR-19 | Scenario tests kept | Scenario store | After a passing run the scenario set SHALL stay in the store with its spec's and contract's fingerprints, generated again when either changed; only dual runs and a separate acceptance step run it, and the acceptance step reports to the person only `[agreed 2026-10-15]` | a later change cannot quietly break a requirement only it checked, and no coder ever sees the result |
| FR-20 | Seam: spec conflicts found | Spec review (`E-INTL-03`) | Spec review SHALL check a spec against the project's existing specs and contracts and name each conflict `[agreed 2026-10-15]` | a spec that contradicts another is caught before any code or scenario is written |
| FR-21 | Normal runs of a project with kept scenarios | Test step, container | In any run of a project whose scenario store holds a set, the coder's tests SHALL run in a container; without one the run SHALL warn and go on `[agreed 2026-10-15]` | outside a dual run too, running code cannot reach the scenario store where a container exists |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | YAML scenarios, not Gherkin | LLMs produce structured data more reliably than natural-language Gherkin **[proof: none — unfalsifiable as written]** |
| NFR-2 | Scenario → pytest is non-LLM | Mechanical conversion eliminates a failure mode and ensures reproducibility |
| NFR-3 | Logging for all pipeline synchronization | Every JOIN wait, fan_out dispatch, and arbiter verdict must produce `logger.info` entries |
| NFR-4 | No test collision | Parallel pipelines must not share filesystem write paths; existing `FolderGrant` enforcement is sufficient |
| NFR-5 | Bounded arbiter retries | At most 2 verdicts that send a side back, each re-running only that side (FR-16); the next failure asks the person `[agreed 2026-10-15]` |
| NFR-6 | Zero `@trace` tag dependency | Tags are comments (`# @trace(FR-X)`), not imports — no runtime dependency |
| NFR-7 | Backward compatibility | All existing pipeline YAML files, gate types, and handler registrations must continue to work unmodified |
| NFR-8 | Total information opacity | The coding agent MUST NOT be able to infer, discover, or be told that a second verification pipeline exists. This includes: (a) no `scenarios/` path in grants, (b) no scenario-related vocabulary in prompts or feedback, (c) arbiter feedback to the coding agent is phrased as spec-derived behavioral assertions — indistinguishable from a reviewer finding. The arbiter feedback MUST read like a review verdict, not a test failure report **[proof: none — unfalsifiable as written]** |

## Repair: surfaces

| FR | Binds to | Verified how |
|---|---|---|
| FR-11, FR-19 | `specweaver_root()` for the data directory; `ScenarioSet(spec_path, contract_path, scenarios, reasoning)`; `ConvertScenarioHandler` writes the test; `output_path(stem, project_root)` per converter | read `core/config/paths.py`, `workflows/scenarios/scenario_models.py:50`, `core/flow/handlers/scenario.py:150-174`, `sandbox/language/core/*/scenario_converter.py` |
| FR-14, FR-18 | `ContainerExecutor` (Podman/Docker, ephemeral; mounts a directory) | read `sandbox/execution/container_executor.py:113-143`; proven for Python projects only |
| FR-5a | `ToolDispatcher._compute_role_grants(role, boundary)` gives `scenario_agent` FULL on `scenarios/` today and nothing under a read-only boundary | read `sandbox/dispatcher.py:163-178` |
| FR-5a | `_build_tool_dispatcher(context, role, adapter)` enables `fs` and `ast`, and `ast` has no `scenario_agent` role (`sandbox/code_structure/interfaces/tool.py:116` raises); `ScenarioGenerator(llm, *, config, max_retries, tool_dispatcher)`; the `generate_with_tools` pattern | read `core/flow/handlers/review.py:37`, `workflows/scenarios/scenario_generator.py:34`, `workflows/review/reviewer.py:190` |
| FR-5b, FR-18 | the sub-run context, a shallow `model_copy()` sharing `feedback` | read `core/flow/engine/fan_out.py:21-43` |
| FR-12 | `_skip_reason`, `_target_task_id` and the payload of the handover; `MemoryHydrator(session, project_name).hydrate()`; the `AGENT_MEMORY` slot | read `core/flow/engine/handover.py:17,63,86`, `workspace/memory/hydrator.py:148`, `core/flow/handlers/prompting.py:63` |
| FR-13 | `_find_and_parse_tests` → `extract_test_mapped_requirements(project_root)`; the walk that prunes directories | read `assurance/validation/rules/code/c09_traceability.py`, `workspace/analyzers/factory.py:221-243` |
| FR-14 | `output_path(stem, project_root)` per converter; `ValidateTestsHandler.execute` for `kind: scenario` | read `sandbox/language/core/*/scenario_converter.py`, `core/flow/handlers/validation.py` |
| FR-15, FR-16, FR-7 | `_spec_sha` (`core/flow/handlers/arbiter.py:137`); the arbiter writes `feedback["generate_code"]`/`["generate_scenarios"]` (`arbiter.py:200,381`); `_build_runner(name, stem, context)`; the `loop_back` to `run_dual_pipelines` that re-runs both sides | read `core/flow/handlers/dual_pipeline.py:44-120`, `core/flow/engine/gates.py:196-234`, `workflows/pipelines/scenario_integration.yaml` |
| FR-17 | role resolution from `settings.toml` | read `infrastructure/llm/resolve.py` (`RoleResolver`) |
| FR-20 | the spec review rubric | read `assurance/validation/rubrics/spec_review.md` (five criteria; none on conflicts) |

`scripts/check_fr_coverage.py` and `scripts/_citations.py` read only `FR-<digits>`, so FR-5a and
FR-5b were never judged; SF-D widens both to `FR-<digits><letter>`.

## Sub-features

FR-14 moved from SF-G to SF-D on 2026-10-15: moving the scenario tests out of the project (FR-11)
works only together with running them from a container mount `[agreed 2026-10-15]`. The repair
re-owns the seven rewritten FRs: each now belongs to the SF that builds or proves its new text, so
every FR has exactly one owner.


The original 11 sub-features (3.28a–j) were merged into three. 3.28g (JOIN gate) and 3.28h
(parallel orchestrator) were already implemented by 3.27.

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-A (3.28a + 3.28b) | S07 checks an optional `## Scenarios` section's YAML; new handler extracts a Python Protocol/ABC from the spec's `## Contract`. | FR-1 (FR-2 moved to SF-F) | spec markdown with `## Contract` → S07 fails on a malformed `## Scenarios`; `contracts/api_contract.py` with a typed Protocol class | none | [sfa](B-FLOW-01_sfa_implementation_plan.md) |
| SF-B (3.28c + 3.28d + 3.28e + 3.28f + 3.28g + 3.28h) | LLM scenario generation from spec + API contract → YAML; mechanical YAML → pytest with `@trace` tags; `scenario_agent` role; **total information opacity** for the coding agent (FR-5b); `scenario_validation.yaml`; dual-pipeline wiring. | FR-4 (FR-3, 5a, 6 moved to SF-F; FR-5b to SF-D; FR-7 to SF-G) | spec, API contract (Protocol class), `req_id` list → `scenarios/definitions/*.yaml` + `scenarios/generated/*.py` (parametrized pytest); two isolated parallel pipelines with JOIN; coding agent unaware of the scenario pipeline | SF-A | [sfb](B-FLOW-01_sfb_implementation_plan.md) |
| SF-B2 | Polyglot scenario pipeline: converters, contract renderers and stack-trace filters for Python, Java, Kotlin, TypeScript, Rust. | — (extends SF-B's FR-4 to more languages; NFR-1, NFR-2) | — | SF-B | [sfb2](B-FLOW-01_sfb2_implementation_plan.md) |
| SF-D | Isolation core: the scenario store outside the project, run from a container mount; each side its own `feedback`; fail closed without a container; the FR checker reads lettered FRs | FR-11, FR-14, FR-5b, FR-18, FR-21 | scenario writes, the sub-run context, the container check → no scenario file in the project, no shared `feedback`, no dual run without isolation | none | [sfd](B-FLOW-01_sfd_implementation_plan.md) |
| SF-E | Memory and coverage apart | FR-12, FR-13 | handover, hydrator, C09 walk → no scenario text in coder memory; C09 counts the coder's tests; a coverage report per requirement | none | [sfe](B-FLOW-01_sfe_implementation_plan.md) |
| SF-F | Scenario side: read-only tools, checked scenarios, filtered reports | FR-5a, FR-3, FR-8, FR-2, FR-6 | spec, contracts → scenarios checked against the spec and the contract; a scenario report with no code | SF-D | [sff](B-FLOW-01_sff_implementation_plan.md) |
| SF-G | Run control: one spec, the side at fault only, models, the scenario run in a container, overlap | FR-15, FR-16, FR-17, FR-7 | the dual run → one reviewed spec; one side per round, 2 rounds; scenario tests run in a container from the store | SF-D | [sfg](B-FLOW-01_sfg_implementation_plan.md) |
| SF-H | Spec conflicts and the kept suite | FR-20, FR-19 | spec review, scenario store → conflicts named at review; scenario sets kept with fingerprints, regenerated on a change, run by dual runs and an acceptance step for the person | SF-D | — |
| SF-C (3.28i + 3.28j) | Arbiter for error attribution, run post-JOIN after `QARunnerAtom` executes scenario tests. **All-read, no-write** boundary (`api_paths` only, zero `roots`). Filtered feedback keeps total information opacity — coding feedback reads like a reviewer finding (AD-9, AD-10). HITL escalation on spec ambiguity. | FR-9, FR-10 (FR-8 moved to SF-F) | scenario test results (pass/fail from QARunnerAtom), spec, API contract, `src/` output, `scenarios/` output → one filtered feedback report per pipeline (vocabulary-filtered per NFR-8), or HITL escalation. Coding feedback has NO scenario vocabulary — phrased as "Spec clause §X requires Y. Your implementation does Z." | SF-B, SF-B2 | [sfc](B-FLOW-01_sfc_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-A | Foundation: Spec Enforcement + Contract Generation | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-B | Scenario Pipeline: Generate + Convert + Wire | SF-A | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-C | Arbiter + Feedback Loop | SF-B | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-D | Isolation core | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-E | Memory and coverage apart | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-F | Scenario side | SF-D | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-G | Run control | SF-D | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-H | Spec conflicts and the kept suite | SF-D | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Now**: SF-F committed — the scenario agent reads `specs/` and `contracts/` only; its scenarios
are checked against the spec and the contract; a class's methods are tested; the arbiter's report
to it holds no code.
**Now**: SF-E committed — a dual run's handover goes to the scenario store, never to task memory; `sw run` ends with which side's tests cover each requirement.
**Next**: the implementation-plan skill for SF-G (run control) or SF-H (spec conflicts and the kept suite).
