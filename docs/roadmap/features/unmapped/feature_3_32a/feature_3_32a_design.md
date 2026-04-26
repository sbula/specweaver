# Design: Adaptive Assurance Standards

- **Feature ID**: 3.32a
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/unmapped/feature_3_32a/feature_3_32a_design.md

## Feature Overview

Feature 3.32a adds adaptive modes ("Mimicry" and "Best Practice") to the `StandardsAnalyzer` component.
It solves the "Empty Repository" context vacuum for greenfield builds by falling back to robust, built-in idiomatic targets instead of failing to extract conventions.
It interacts with `StandardsAnalyzer`, `specweaver.toml` configuration parsers, and prompt injection loops while strictly avoiding architectural boundary violations.
Key constraints: must rigorously adhere to all `.yaml` contexts, enable ROI-driven refactoring across domains, and optimize overall performance by addressing redundancies.

## Research Findings

### Codebase Patterns
Currently, `StandardsAnalyzer` heavily relies on AST extraction across all scopes to extract naming and architecture constraints. For greenfield repos, this results in an "Empty Repository" vacuum since it expects legacy code. We can reuse the `tree-sitter` bindings inside `commons/language/ast_parser.py` but we must build a secondary pipeline logic layer inside `assurance/standards` to provide built-in profiles.  
Based on the explicit request for **ROI analysis and optimization**, an analysis of the Phase 3 Optimizations (`docs/architecture/feature_3_32d_refactoring_design.md`) reveals a massive architectural return in embedding **AST Skeleton Condensation** (1.1). Replacing raw contiguous content dumps with deterministic signatures directly limits the token blast radius and speeds up context resolution, providing immediate structural speed enhancements when injecting standards.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| tree-sitter | * | AST extraction | `commons/language` |

### Blueprint References
- Feature 3.32d Refactoring Design (Phase 3 Optimizations)

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse configurable standard targets | System | Reads `specweaver.toml` | Returns targeted mode ("mimicry" vs "best_practice") |
| FR-2 | Fallback to Built-in Context | StandardsAnalyzer | Detects "best_practice" mode | Injects scaffolding configuration defaults mapped from `context.db` profiles without executing `loom` execution tools |
| FR-3 | Condense Context via Skeletons | PromptBuilder | Modifies injected metadata | Redundant context data is truncated into purely deterministic AST Skeletons for maximum optimization |
| FR-4 | Implement Safe Graph Referencing | TopologyGraph | Reads file topologies intelligently | Executes dependency bounds referencing without reloading files natively to improve cycle speeds |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Boundary Compliance | `StandardsAnalyzer` must never invoke `loom/*` tools natively per `context.yaml` `forbids` rules. |
| NFR-2 | Performance ROI | System must achieve token size reductions without decreasing accuracy. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| tree-sitter | N/A | Parsing syntax | Y | Already integrated within project |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Scaffold Config Defaults via Database | Bypasses the need to create generic default AST logic natively into code; leverages `config` layer pure logic mapping. | No |
| AD-2 | AST Skeleton Condensation Injection | Replaces monolithic context window appending with deterministic signature indexing natively in the compiler boundaries. Provides vast performance ROI by minimizing token costs. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Adding Built-in Standards | How to contribute explicit idiomatic standards targeting new languages. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Adaptive Standard Configurations
- **Scope**: Toggle logic in `StandardsAnalyzer` and configuration parsing for "mimicry" vs "best_practice" and mapping historical `context.db` defaults.
- **FRs**: [FR-1, FR-2]
- **Inputs**: `specweaver.toml` config settings, greenfield target paths.
- **Outputs**: Resolved built-in standard rules payloads.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/unmapped/feature_3_32a/feature_3_32a_sf1_implementation_plan.md

### SF-2: Context Condensation Skeletons (Performance ROI)
- **Scope**: Integration of AST extraction skeletons natively into the context layer limiting token payload sizes.
- **FRs**: [FR-3, FR-4]
- **Inputs**: Legacy source dependencies topological structures.
- **Outputs**: Truncated prompt boundaries reflecting identical semantic data maps.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/unmapped/feature_3_32a/feature_3_32a_sf2_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Adaptive Standard Configurations | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Context Condensation Skeletons | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: [x] Feature 3.32a fully implemented! SF-1 and SF-2 are merged.
**Next step**: Select the next feature from the roadmap.
