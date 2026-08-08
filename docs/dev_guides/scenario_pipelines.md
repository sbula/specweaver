# Scenario Pipelines Developer Guide

This guide explains the Scenario Testing framework introduced in Feature 3.28 (`B-FLOW-01`), which builds on top of the parallel engine (Feature 3.27) to provide an independent, LLM-driven verification loop separate from the main implementation pipeline.

> [!IMPORTANT]
> **Updated for `INT-US-24` (2026-07-24)** — the base integration contract made this chain real:
>
> - **CLI journey**: `sw run scenario_integration <spec>` runs the whole chain (contract →
>   dual fan-out → scenario tests → arbiter loop). Exit codes: COMPLETED → 0; FAILED/retries
>   exhausted → non-zero; `spec_ambiguity` HITL park → 0 + resume hint. `sw resume` re-runs a
>   fresh verification round (scenario evidence is NOT persisted across sessions — the honest
>   arbiter error trips the loop_back and the round re-executes; verified by proof scenario E7).
> - **Evidence contract**: for scenario runs `ValidateTestsHandler` publishes the raw QA export
>   under `context.feedback["scenario_test_failures"]`; the arbiter consumes it on verdict —
>   green (`total>0, failed==0, errors==0`) short-circuits with ZERO LLM cost; `total==0`
>   fails loud; absent/malformed evidence is a loud error.
> - **Scenario-kind semantics**: `kind: scenario` is a flow-level category, NOT a pytest
>   marker; a scenario run collecting 0 tests FAILS (never a silent green).
> - **REAL test bodies**: the mechanical converter emits genuine tests — a file-anchored
>   importlib loader (stem chosen by the handler, never by LLM data), `target(**inputs)`
>   calls, equality asserts on `expected_output`, `pytest.raises` for error-category. Groups
>   are `(function, category)`-keyed. Emitted names/values go through identifier validation
>   and `repr()` — LLM content cannot inject statements.
> - **Verifiable proof**: `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py`
>   (E1–E8 on the real CLI).
>
> **Host-posture facts (until `C-EXEC-07` contains runs in worktrees):** scenario artifacts
> (`contracts/`, `scenarios/definitions/`, `scenarios/generated/`) persist in your repo on
> failed/aborted runs, and `scenarios/generated/test_*.py` is collectable by a bare `pytest`
> at repo root — exclude that directory in your pytest config if you don't want verification
> artifacts in your own test runs.

## Overview

Traditional agentic generation pipelines use a single LLM to write tests and implementation. This creates a "Correlated Hallucination" problem: if the LLM misunderstands a requirement, it writes both the implementation and the test with the same misunderstanding, causing the tests to pass despite the code being incorrect.

SpecWeaver solves this via a **Dual-Pipeline Architecture**:
1. **Coding Pipeline**: Focuses purely on writing implementation code against `Spec.md`.
2. **Scenario Pipeline**: Focuses purely on writing structured `YAML` scenarios against an API contract, which are mechanically translated into parameter-driven tests.

These pipelines execute **in parallel**, completely blind to each other, and rendezvous at a topological `JOIN` gate.

## The Scenario Agent (`scenario_agent`)

To enforce mathematical independence, the scenario agent operates under strict `ROLE_INTENTS` constraints in `FileSystemTool`:

- It is **read-only** on `specs/` and `contracts/` directories.
- It is **read-write** only isolated inside the `scenarios/` directory. 
- It CANNOT read implementation source code under `src/`.
- It CANNOT read the coding agent’s internal scratchpads.

Similarly, the coding agent has zero access to the `scenarios/` directory.

## Pipeline Architecture: `scenario_validation.yaml`

The scenario generation process is orchestrated via `scenario_validation.yaml`. It follows a strict sequence:

1. **Extract Contract** (`generate+contract`): Extracts a python Protocol/ABC from the Spec's `Contract` section.
2. **Generate Scenarios** (`generate+scenario`): Analyzes the generated contract + Spec and emits `scenarios/definitions/<name>.yaml` using declarative structured output.
3. **Convert to Tests** (`convert+scenario`): Pure-logic step (Zero LLM) that reads the YAML and translates it directly to parameterized `pytest` tests annotated with `# @trace(FR-X)` tags to satisfy Rule `C09_traceability`.

## Generating Scenarios

The `GenerateScenarioHandler` uses the `ScenarioGenerator` component (which closely mimics `Planner`), operating with:
- An LLM injection containing the API Contract Context.
- `ScenarioDefinition` models utilizing Pydantic JSON schemas.
- Automatic retries on malformed outputs or incorrect bounds. 

## The Topological `JOIN` Gate

Because both `new_feature.yaml` (coding tree) and `scenario_validation.yaml` (scenario tree) run in parallel, SpecWeaver coordinates file locks over shared outputs via the `GateType.JOIN` parameter.

The parent orchestration step maps sub-components and fires `run_fan_out()`. The OS physical write lock wait-queue activates transparently because the JOIN blocks progression of either sub-child branch into phase 4 (test execution) until both the scenario files and the implementation files are persisted.

## The Arbiter Feedback Loop

After the topological JOIN gate completes, the parent pipeline triggers test execution and finally the **Arbiter** (`ArbitrateVerdictHandler`). 

If scenarios fail, the Arbiter's job is fault attribution. It evaluates to either `code_bug`, `scenario_error`, or `spec_ambiguity`.

To maintain total opacity, the Arbiter sends **vocabulary-filtered feedback** to the Coding Agent:
- It translates "The scenario test validation failed" into "The spec says X, but your code did Y."
- The Coding Agent NEVER sees the scenario test code or the word "scenario".
- If it determines a `spec_ambiguity`, it escalates to the human via a HITL gate.

This prevents the Coding Agent from simply hardcoding against the generated test logic, forcing it to continually refer back to the original Spec requirement traces.

---

**See Also:**
- [Pipeline Engine Guide](pipeline_engine_guide.md)
- [Layer Isolation and DI](layer_isolation_and_di.md)
