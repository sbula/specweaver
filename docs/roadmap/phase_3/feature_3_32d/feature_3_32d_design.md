# Design: Refactoring Phase 3 Optimizations

- **Feature ID**: 3.32d
- **Phase**: 3
- **Status**: DRAFT
- **Design Doc**: docs/roadmap/phase_3/feature_3_32d/feature_3_32d_design.md

## Feature Overview

Feature 3.32d adds Refactoring Phase 3 Optimizations to the core engine, flow pipeline, and validation architecture. It solves high latency, token over-spend, LLM "Blank Canvas" hallucination, and full-test suite slowness by applying Context Condensation (AST Skeletons), topology-based specific Pytest limiting, CI-safe validation, and standard scaffolding upon `sw init`. It interacts with `PromptBuilder`, `PolyglotQARunner`, DAL/CLI bounds, and project constraints engine, and does NOT touch git operations, front-ends, or remote LLM server configuration. Key constraints: Condensation preserves exact editing targets; DAL yields non-zero exits strictly; `sw init` scaffolding forbids LLM execution (`loom` boundary compliance).

## Research Findings

### Codebase Patterns
- **Context Condensation**: The `PromptBuilder` already exists at `src/specweaver/infrastructure/llm/prompt_builder.py`. The `CodeStructureTool` and `CodeStructureAtom` already extract AST sequences per language. We can reuse these tools by passing file blocks through `CodeStructureAtom` to degrade non-target contextual files.
- **Impact-Aware Test Limiting**: `QARunnerAtom` executes pytest flows locally. We can inject limits by querying `TopologyGraph.stale_nodes()` in orchestrators like `ValidationRunner` or `PipelineRunner` and passing `--test-target` arguments to `QARunnerAtom.run_tests()`.
- **CI/CD Risk Evaluation**: We already have `sw scan --standards`. We can extend `src/specweaver/interfaces/cli/` to bind a unified pipeline sweep that natively returns a `typer.Exit(code=1)` upon threshold breaches.
- **Project Standards Scaffolding**: `workspace/project/scaffold.py` handles `sw init`. It must be extended to scaffold standard `context.yaml` boundaries and rule templates statically without touching the `loom` (Agent) boundary to avoid cyclic LLM execution constraints.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Pytest | >7.0 | Targeted execution via `--pyargs` or explicit paths | Web Research (Test Impact Analysis patterns) |

### Blueprint References
- None explicitly mapped for 3.32d; references CI patterns from PasteMax and Testmon.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Context Condensation | PromptBuilder | Process `context_files` | De-duplicate and condense contextual non-target files into strictly typed AST Skeletons via `CodeStructureAtom`, halving token usage. |
| FR-2 | Test Limiting | QARunnerAtom | Limit Pytest scope | Execute tests explicitly scoped to `TopologyGraph.stale_nodes` and their direct dependents instead of the global `tests/` directory. |
| FR-3 | CI/CD Runner | CLI (`sw scan`) | Evaluate `sw scan --ci` | Run validation standards pipeline strictly dynamically and emit a non-zero exit code if the DAL threshold breaches standard tolerances. |
| FR-4 | Starter Scaffolding | Project Scaffold | Initialize Project | Emit default standard topologies into `context.yaml` without importing `.loom` tools or querying an LLM in the initialization chain. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Skeleton condensation must be <1.0s to avoid latency build-up per loop. |
| NFR-2 | Architecture Compliance | The CI/CD sweep (`sw scan --ci`) must execute under stateless execution mode (`operational.async_ready = false`). |
| NFR-3 | Compatibility | Pytest targeting must not conflict with parameterized `[ ]` paths on Windows CMD consoles. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| tree-sitter | 0.21.0 | Language parsers | Y | Included natively via Feature 3.22 Polyglot Extractors |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Query TopologyGraph statically in QARunnerTool | Bypasses complex dependency injection from `PipelineRunner` by locally constructing the topology slice before pytest execution. | Yes |
| AD-2 | Hardcode AST Skeleton truncation within PromptBuilder natively. | Centralizes token preservation logic rather than asking Handlers to manually parse file sizes. | No |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Test Impact Testing | Using stale tracking to bypass full suite testing natively | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Context Condensation & Scaffolding
- **Scope**: Implements AST Skeleton logic in `PromptBuilder` and scaffolds native `context.yaml` profiles on `sw init`.
- **FRs**: [FR-1, FR-4]
- **Inputs**: Polyglot parsers, `PromptBuilder` context lists, CLI initialization paths.
- **Outputs**: Truncated XML payloads and initialized `.specweaver/` structures.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3_32d/feature_3_32d_sf1_implementation_plan.md

### SF-2: Impact-Aware Testing & CI/CD Limits
- **Scope**: Re-wires `QARunnerTool` to filter targets via the Topology Graph and implements the `--ci` limit gate to exit non-zero statically.
- **FRs**: [FR-2, FR-3]
- **Inputs**: DAG nodes, Pytest targets, `sw scan --ci` CLI input.
- **Outputs**: Truncated Pytest stdout logs, and non-zero OS level exit boundaries.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/phase_3/feature_3_32d/feature_3_32d_sf2_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Context Condensation | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-2 | Impact-Aware Testing | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-1 Impl Plan APPROVED.
**Next step**: After approval, run:
/dev docs/roadmap/phase_3/feature_3_32d/feature_3_32d_sf1_implementation_plan.md
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.