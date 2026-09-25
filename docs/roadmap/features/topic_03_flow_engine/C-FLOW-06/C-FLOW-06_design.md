# C-FLOW-06 — Refactoring Phase 3 Optimizations

**Status**: DRAFT · **Feature ID**: 3.32d · **Phase**: 3 · SF-01 committed; SF-02 halted — open
items in [README_BEFORE_CONTINUE.md](README_BEFORE_CONTINUE.md).

| | |
|---|---|
| Uses | `PromptBuilder`, `CodeStructureAtom` / `CodeStructureTool`, `QARunnerAtom` / `PolyglotQARunner`, `DALResolver`, `TopologyGraph` |
| Not touched | git operations, front-ends, remote LLM server configuration |

## What it does

Four optimizations against latency, token over-spend, "Blank Canvas" hallucination and slow full-suite
test runs:

- **Context condensation** — non-target context files go to the LLM as AST skeletons.
- **Impact-aware test limiting** — pytest runs only the tests of stale topology nodes.
- **DAL enforcement** — validation respects DAL strictness and exits non-zero on a breach.
- **Starter scaffolding** — `sw init` writes default `context.yaml` boundaries.

Constraints: condensation preserves the exact editing targets; DAL enforcement yields a non-zero
exit without a CLI flag; `sw init` scaffolding runs no LLM (`loom` boundary compliance).

## Where it plugs in

- **Condensation**: `PromptBuilder` (`src/specweaver/infrastructure/llm/prompt_builder.py`).
  `CodeStructureTool` and `CodeStructureAtom` already extract AST per language; non-target context
  files pass through `CodeStructureAtom` and are degraded to skeletons.
- **Test limiting**: `QARunnerAtom` runs pytest locally. An orchestrator (`ValidationRunner` /
  `PipelineRunner`, per AD-1 `ValidateTestsHandler`) queries `TopologyGraph.stale_nodes()` and
  passes `--test-target` paths to `QARunnerAtom.run_tests()`.
- **DAL**: `DALResolver` sits inside `PipelineRunner`, so all validation respects DAL strictness
  thresholds and exits with `typer.Exit(code=1)` on a breach — no CLI-specific flag.
- **Scaffolding**: `workspace/project/scaffold.py` handles `sw init`. It writes `context.yaml`
  boundaries and rule templates statically, never touching the `loom` (Agent) boundary — that would
  create cyclic LLM execution.

External: Pytest >7.0 (targeted runs via `--pyargs` or explicit paths; Test Impact Analysis
patterns); tree-sitter 0.21.0 (language parsers, compat confirmed, shipped with Feature 3.22
Polyglot Extractors). Prior art: CI patterns from PasteMax and Testmon; no blueprint.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Query TopologyGraph dynamically in ValidateTestsHandler (REJECTED QARunnerTool static query) | `loom/` (Execution Layer) must not import `graph/` (Pure Logic). `ValidateTestsHandler` may consume `graph/` and passes resolved paths into `QARunnerAtom`. | Yes |
| AD-2 | Hardcode AST Skeleton truncation within PromptBuilder. | Token-saving logic in one place, instead of each Handler parsing file sizes. | No |

AD-1 replaced "Query TopologyGraph statically in QARunnerTool": that made `loom` import `graph`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Context Condensation | PromptBuilder | Process `context_files` | De-duplicate and condense contextual non-target files into strictly typed AST Skeletons via `CodeStructureAtom`, halving token usage. |
| FR-2 | Test Limiting | QARunnerAtom | Limit Pytest scope | Execute tests explicitly scoped to `TopologyGraph.stale_nodes` and their direct dependents instead of the global `tests/` directory. |
| FR-3 | Validation DAL Gates | Core Framework | DAL Enforcement | Integrate `DALResolver` into `PipelineRunner` and CLI commands so all validation respects DAL strictness thresholds, exiting 1 when breached (Fail-at-end). |
| FR-4 | Starter Scaffolding | Project Scaffold | Initialize Project | Emit default standard topologies into `context.yaml` without importing `.loom` tools or querying an LLM in the initialization chain. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Skeleton condensation must be <1.0s to avoid latency build-up per loop. |
| NFR-2 | Architecture Compliance | Validation pipelines must execute cleanly under stateless execution mode (`operational.async_ready = false`). |
| NFR-3 | Compatibility | Pytest targeting must not conflict with parameterized `[ ]` paths on Windows CMD consoles. |

## Guides owed

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Test Impact Testing | Using stale tracking to bypass full suite testing | ⬜ To be written during Pre-commit |

## Sub-features

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-01 | AST skeletons in `PromptBuilder`; `context.yaml` profiles on `sw init` | FR-1, FR-4 | polyglot parsers, `PromptBuilder` context lists, CLI init paths → truncated XML payloads, initialized `.specweaver/` | — | [sf01](C-FLOW-06_sf01_implementation_plan.md) |
| SF-02 | Test targets filtered via the Topology Graph; DAL boundaries fail validation | FR-2, FR-3 | DAG nodes, pytest targets, `DALResolver` thresholds → truncated pytest stdout, non-zero exit | SF-01 | [sf02](C-FLOW-06_sf02_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Context Condensation | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Impact-Aware Testing & DAL | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

**Next**: SF-02 Dev — see [README_BEFORE_CONTINUE.md](README_BEFORE_CONTINUE.md).
