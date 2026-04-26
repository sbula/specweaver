# Design: AST Drift Detection & AI Root-Cause Analysis

- **Feature ID**: 3.14a
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_05_validation/B-VAL-01/B-VAL-01_design.md

## Feature Overview

Feature 3.14a adds deep, parser-backed drift detection to SpecWeaver. It leverages the Artifact Lineage UUIDs established in Feature 3.14 to traverse the graph to the structured Plan JSON generated during Phase 3.6. By extracting the AST of the running code and comparing it structurally to this pure JSON representation of the spec's intent, it autonomously identifies human-introduced implementation drift and coverage gaps. Additionally, it offers an opt-in mode to use LLMs to pinpoint the root cause of any detected violations. It interacts with the existing validation pipeline and the flow engine, and does NOT touch real-time background file watching. Key constraints: The AST gap analysis must be fast (no LLM required for the core AST check) to keep the feedback loop tight.

## Research Findings

### Codebase Patterns
- We already have AST parsing capabilities (`standards/tree_sitter_base.py`) which we can inherit/leverage.
- Artifact tracking via `# sw-artifact` UUIDs is fully implemented in DB by 3.14.
- `validation/` pure-logic layer is where we evaluate spec/code rules. A new pure-logic component `validation/drift_detector.py` perfectly fits here.
- `flow/` engine manages dispatching commands and logging LLM operations. LLM pinpointing belongs in an orchestration handler (`flow/_drift.py`).
- No boundary rules are violated by orchestrating `validation` + `llm` from `flow/`. 

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| tree-sitter | 0.22+ | `.parse()`, node queries | Python Package |

### Blueprint References
None specified in ORIGINS.md beyond the high-level roadmap.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | AST Extraction | System | SHALL extract the Abstract Syntax Tree (AST) of the target file using `tree_sitter` | AST representation is produced for analysis |
| FR-2 | Baseline Fetch | System | SHALL fetch the Structured Plan JSON via the file's lineage UUID | Structural baseline is established |
| FR-3 | Drift Detection | System | SHALL detect structural mutations in the AST compared to the baseline spec expectations | A list of drift findings is produced |
| FR-4 | Gap Analysis | System | SHALL evaluate coverage by verifying AST nodes corresponding to spec scenarios exist | Missing scenarios are reported as coverage gaps |
| FR-5 | Root-Cause Analysis | System | SHALL trigger LLM root-cause analysis on detected drift ONLY when `--analyze` is passed | Explains why the drift happened |
| FR-6 | Drift CLI | Developer | SHALL run `sw drift check <file> [--analyze]` | Initiates structural inspection pipeline |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | AST drift check execution (without `--analyze`) MUST take < 500ms |
| NFR-2 | Safety | Must be strictly read-only; never mutate source files or specification files |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| tree-sitter | 0.22 | AST node traversal | Yes | Pre-installed for `standards/` feature |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Put detector logic in `validation/` | Pure-logic component that compares AST to an expected criteria. Matches existing `validation/rules` pattern. | No |
| AD-2 | Put LLM integration in `flow/_drift.py` | `validation` layer forbids `llm` imports. Orchestration happens in the `flow/` runner. | No |
| AD-3 | Explicit `--analyze` flag | LLM analysis can be expensive. Fast structural static checking must be the default. | No |
| AD-4 | Structural Baseline via Phase 3.6 Plan | Extracts the structured JSON Plan instead of markdown parsing or AST caching. Ensures "Spec is truth" architecture. | No |

## Sub-Feature Breakdown

### SF-1: AST Drift & Coverage Engine
- **Scope**: Core pure-logic component combining AST parser with Spec rule comparative matching.
- **FRs**: [FR-1, FR-2, FR-3, FR-4]
- **Inputs**: Source code file path and its parent Spec constraints (via `models`).
- **Outputs**: Structured drift and coverage findings (no LLM involved).
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_05_validation/B-VAL-01/B-VAL-01_sf1_implementation_plan.md

### SF-2: Flow Integration & CLI (`sw drift`)
- **Scope**: Expose the detector to pipelines and the CLI, providing opt-in LLM root-cause pinpointing.
- **FRs**: [FR-5, FR-6]
- **Inputs**: User CLI arguments, findings from SF-1, and UUIDs from DB context.
- **Outputs**: Pipeline step execution, terminal rendering, and an LLM root-cause response if requested.
- **Depends on**: [SF-1]
- **Impl Plan**: docs/roadmap/features/topic_05_validation/B-VAL-01/B-VAL-01_sf2_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | AST Drift Engine | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Flow Integration & CLI | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Implementation Plan APPROVED for SF-2. Ready for Flow Validation & CLI development.
**Next step**: Run TDD workflow: `/dev docs/roadmap/features/topic_05_validation/B-VAL-01/B-VAL-01_sf2_implementation_plan.md`
