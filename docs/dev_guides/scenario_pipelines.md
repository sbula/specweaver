# Scenario Pipelines

Use when: you work on the scenario testing framework (Feature 3.28, `B-FLOW-01`): the independent,
LLM-driven verification loop that runs beside the implementation pipeline on the parallel engine
(Feature 3.27).

## Why two pipelines

One LLM writing both code and tests causes "Correlated Hallucination": a misread requirement ends up
in both, and the tests pass on wrong code. SpecWeaver runs a **Dual-Pipeline Architecture**:

1. **Coding Pipeline**: writes implementation code against `Spec.md`.
2. **Scenario Pipeline**: writes structured `YAML` scenarios against an API contract; these are
   mechanically translated into parameter-driven tests.

Both run **in parallel**, blind to each other, and meet at a topological `JOIN` gate.

## Running it

`sw run scenario_integration <spec>` runs the whole chain (contract → dual fan-out → scenario
tests → arbiter loop). Base integration contract: `INT-US-24` (2026-07-24).

| Outcome | Exit code |
|---|---|
| COMPLETED | 0 |
| FAILED/retries exhausted | non-zero |
| `spec_ambiguity` HITL park | 0 + resume hint |

`sw resume` runs a fresh verification round. Scenario evidence is NOT persisted across sessions: the
arbiter's honest error trips the loop_back and the round re-executes (proof scenario E7).

Proof: `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py` (E1–E8 on the real CLI).

## The scenario agent (`scenario_agent`)

`ROLE_INTENTS` in `FileSystemTool` keep it independent:

- **read-only** on `specs/` and `contracts/`.
- **read-write** only inside `scenarios/`.
- CANNOT read implementation source under `src/`.
- CANNOT read the coding agent's scratchpads.

The coding agent has zero access to `scenarios/`.

## Pipeline: `scenario_validation.yaml`

1. **Extract Contract** (`generate+contract`): a python Protocol/ABC from the Spec's `Contract`
   section.
2. **Generate Scenarios** (`generate+scenario`): reads contract + Spec, emits
   `scenarios/definitions/<name>.yaml` via declarative structured output.
3. **Convert to Tests** (`convert+scenario`): pure logic, zero LLM. Translates the YAML into
   parameterized `pytest` tests tagged `# @trace(FR-X)` for Rule `C09_traceability`.

`GenerateScenarioHandler` uses `ScenarioGenerator` (modelled on `Planner`) with the API Contract
Context injected, `ScenarioDefinition` Pydantic JSON schemas, and automatic retries on malformed
output or wrong bounds.

## Converter output

The converter emits real tests:

- a file-anchored importlib loader (stem chosen by the handler, never by LLM data);
- `target(**inputs)` calls with equality asserts on `expected_output`;
- `pytest.raises` for the error category;
- groups keyed by `(function, category)`.

Emitted names/values pass identifier validation and `repr()`: LLM content cannot inject
statements.

## The `JOIN` gate

`new_feature.yaml` (coding tree) and `scenario_validation.yaml` (scenario tree) run in parallel;
`GateType.JOIN` coordinates file locks on shared outputs. The parent step maps sub-components and
calls `run_fan_out()`. The JOIN holds both branches before phase 4 (test execution) until scenario and
implementation files are persisted; the OS write-lock wait-queue does the rest.

## Evidence and the Arbiter

After the JOIN, the parent runs the tests, then the **Arbiter** (`ArbitrateVerdictHandler`).

Evidence contract:

- `ValidateTestsHandler` publishes the raw QA export under
  `context.feedback["scenario_test_failures"]`.
- Green (`total>0, failed==0, errors==0`) short-circuits with ZERO LLM cost.
- `total==0` fails loud; absent/malformed evidence is a loud error.
- `kind: scenario` is a flow-level category, NOT a pytest marker. A scenario run collecting 0 tests
  FAILS, never a silent green.

On failure the Arbiter attributes fault: `code_bug`, `scenario_error`, or `spec_ambiguity`.

- Feedback to the Coding Agent is **vocabulary-filtered**: "The scenario test validation failed"
  becomes "The spec says X, but your code did Y."
- The Coding Agent NEVER sees scenario test code or the word "scenario", so it cannot hardcode
  against the tests and must follow the Spec's requirement traces.
- `spec_ambiguity` escalates to a human via a HITL gate.

## Traps

- Until `C-EXEC-07` runs these in worktrees, scenario artifacts (`contracts/`,
  `scenarios/definitions/`, `scenarios/generated/`) stay in your repo after failed/aborted runs.
- `scenarios/generated/test_*.py` is collectable by a bare `pytest` at repo root. Exclude that
  directory in your pytest config to keep verification artifacts out of your own test runs.

## See also

- [Pipeline Engine Guide](pipeline_engine_guide.md)
- [Layer Isolation and DI](layer_isolation_and_di.md)
