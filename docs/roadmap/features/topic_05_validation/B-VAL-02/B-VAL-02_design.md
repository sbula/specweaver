# Design: Bi-Directional Spec Rot Interceptor

- **Feature ID**: 3.23
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_05_validation/B-VAL-02/B-VAL-02_design.md

## Feature Overview

Feature 3.23 solves the "2nd-Day Problem" by blocking builds/commits if the implementation AST diverges from `Spec.md`, forcing developers to reconcile documentation with hot-fixes. It is implemented as a git pre-commit hook mapping to a standalone `sw check-rot --staged` CLI command. It does NOT touch out-of-scope system modules or mutate existing pipelines, remaining orthogonal to internal LLM flows and validation state. Key constraints include no LLM/AI calls for checks (purely deterministic) and operating strictly within `tach` layer boundaries via Single-Step `flow` delegation.

## Research Findings

### Codebase Patterns
- `cli` forbids importing from `loom/*`. The CLI command `sw check-rot` cannot directly instantiate the `CodeStructureTool` or AST language extraction utilities.
- `cli/drift.py` shows how to bypass this restrictions gracefully: the CLI defines a dynamic one-step pipeline (`PipelineDefinition.create_single_step`) and runs it with `PipelineRunner`.
- Feature 3.22 implemented Polyglot AST extraction via `AstAtom`, which we will reuse.
- Traceability extraction logic in `c09_traceability.py` confirms that structural detection of `@trace` nodes from `tree-sitter` parsed source bytes works correctly.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| `tree-sitter` | Latest | `Parser`, AST Parsing | `pyproject.toml` |
| Git | Standard | `.git/hooks/pre-commit` | Subprocess / script |

### Blueprint References
- Extends the core BDD architecture patterns and BDD Traceability concepts discussed in `ORIGINS.md`.
- Adheres to the Architecture Reference strict bounds for CLI/Loom boundaries.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Deploy Hook | CLI Command | executes `sw githook install --pre-commit` | The system SHALL create/overwrite the `.git/hooks/pre-commit` shell script in the project workspace. |
| FR-2 | Trigger Interceptor | Git Pre-commit | executes `sw check-rot --staged` | The system SHALL intercept the active commit attempt. |
| FR-3 | Stage Filtering | Interceptor Command | evaluates the current git index | The system SHALL identify all staged target files using `git diff --cached --name-only` and skip out-of-scope files. |
| FR-4 | Pipeline Delegation | Interceptor Command | delegates to engine | The system SHALL execute a dynamic one-step pipeline `DETECT ROT` targeting `StepTarget.DRIFT`. |
| FR-5 | Extract Signatures | Rot Handler | analyzes staged AST | The system SHALL leverage `AstAtom` (Polyglot AST Extractor) to extract method signatures and `@trace` metadata from the staged files. |
| FR-6 | Read Specs | Rot Handler | reads requirement sources | The system SHALL correctly locate and load the associated `Spec.md` requirements tied to the AST objects via traceability tags. |
| FR-7 | Correlate Drift | Rot Handler | matches AST against Spec | The system SHALL emit a FAILED `StepResult` with severity ERROR if divergence between the Code AST structure and the Spec.md contract is detected. |
| FR-8 | Block Commit | Interceptor Command | reads the pipeline result | The system SHALL exit with a non-zero deterministic code (`1`) to explicitly abort the git commit process if `StepResult` is FAILED. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Latency | The `check-rot` command MUST execute within `<500ms` for average commits. No LLM calls allowed. |
| NFR-2 | Architectural Bounds | The `cli` layer MUST NOT directly import or execute AST parsing tools from `loom/*`, utilizing the `PipelineRunner` mechanism instead. |
| NFR-3 | Compatibility | The generated pre-commit hook MUST be compatible with standard POSIX bash shells (applicable to macOS, Linux, and Windows Git Bash environments). |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| `tree-sitter` | Current | `Parser`, AST nodes | Yes | Pre-existing in `loom/commons` |
| `git` | Standard | hooks/pre-commit | Yes | Standard CLI usage |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Native Pre-Commit Hook | Aligns with the core vision. Stops developers at the exact local ledger entry point. | No |
| AD-2 | CLI Flow Delegation | Standard SpecWeaver pattern. Isolates loom usage from the CLI command boundaries. | No |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Spec Rot Pre-Commit Workflow | Explains how to install the rot interceptor hook locally, what errors signify, and how developers resolve blocks by updating Spec/Code. | ✅ Completed (`docs/dev_guides/spec_rot_pre_commit_workflow.md`) |

## Sub-Feature Breakdown

### SF-1: CLI Command + Git Hook Deployment
- **Scope**: Expose the git hook installation logic and the bare entry point for the `sw check-rot --staged` command.
- **FRs**: [FR-1, FR-2, FR-3]
- **Inputs**: CLI trigger (`sw githook install --pre-commit`) and the git execution environment calling `sw check-rot --staged`.
- **Outputs**: The generated bash script artifact in `.git/hooks/pre-commit` and the isolated CLI interface passing target files downstream.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_05_validation/B-VAL-02/B-VAL-02_sf1_implementation_plan.md

### SF-2: Dynamic Flow Handler (Detect Rot)
- **Scope**: Construct the engine logic to dynamically pull AST structures via atoms, compare signatures to `Spec.md`, and report step conclusions.
- **FRs**: [FR-4, FR-5, FR-6, FR-7, FR-8]
- **Inputs**: Staged file paths from SF-1.
- **Outputs**: Output `StepResult` defining if the commit should fail, complete with deterministic findings arrays to halt the execution shell.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_05_validation/B-VAL-02/B-VAL-02_sf2_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | CLI Command + Git Hook Deployment | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Dynamic Flow Handler (Detect Rot) | SF-1 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Impl Plan SF-2 APPROVED.
**Next step**: Run:
`/dev docs/roadmap/features/topic_05_validation/B-VAL-02/B-VAL-02_sf2_implementation_plan.md`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
