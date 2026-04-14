# Scenario Pipelines Developer Guide

This guide explains the Scenario Testing framework introduced in Feature 3.28, which builds on top of the parallel engine (Feature 3.27) to provide an independent, LLM-driven verification loop separate from the main implementation pipeline.

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

---

**See Also:**
- [Pipeline Engine Guide](pipeline_engine_guide.md)
- [Layer Isolation and DI](layer_isolation_and_di.md)
