# Design: Automated iterative decomposition (multi-level)

- **Feature ID**: 3_24
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3_24/feature_3_24_design.md

## Feature Overview

Feature 3.24 (Automated iterative decomposition) adds recursive, multi-level decomposition (feature → sub-features → components) to the `flow` engine.
It solves the manual bottleneck of building component specs by taking DMZ-style iterative loop principles, wrapping decomposition in an automated loop with quality gates, and fanning out until all components are mapped.
It interacts with `pipeline` and `flow` runners, `drafting/decomposition.py`, and the CLI. It does NOT touch unrelated feature areas.
Key constraints: The decomposition process must pause and request HITL review for every structural generation step (never auto-decompose without verification).

## Research Findings

### Codebase Patterns
- Currently, `DecomposeHandler` doesn't exist natively integrated for full recursive pipelines, but `drafting/decomposition.py` contains `ComponentChange`, `IntegrationSeam`, and `DecompositionPlan`.
- The `feature_decomposition` pipeline runs draft->validate->decompose.
- We need to introduce an orchestration loop in the pipeline runner or a specialized macro-pipeline that uses `loop_back` to recursively handle the results of the decomposition.
- We must respect `tach.toml` and existing layer bounds. The orchestration belongs securely in `flow/`.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Tree-sitter | N/A | N/A | N/A |

### Blueprint References
- `docs/analysis/methodology_open_research.md` §1 (Automated Decomposition)
- `docs/analysis/future_capabilities_reference.md` §18

## Design Philosophy: Global Optimization vs Local Execution

To ensure this knowledge persists across agent handoffs, the following architectural constants define how automated decomposition behaves:

1. **Global vs Local Maxima:** 
   - The *L2 Architect Agent* is explicitly exempt from feature size limits (`> 5 FRs`). During the `plan` and `decompose` steps, it ingests the entire monolithic scope to determine the absolute global optimum (shared data models, core modules).
   - The *L4 Developer Agents* are strictly confined to the resulting subdivided Component Specs (the local scope). They may locally optimize functions but are mathematically restricted from cross-polluting architecture via the `ValidationGate`.
2. **Mock-First Interface Definition:** 
   - Slicing relies on `IntegrationSeam` structs produced during the decomposition step. Interfaces (API endpoints, public class signatures, events) MUST be defined and agreed upon *before* any sub-feature code generation begins (`future_capabilities_reference.md` §7).
3. **Granularity Thresholds:**
   - A sub-feature is recursively split if it fails the "Agent-Sized Heuristic" (e.g., handles $>5$ FRs, touches $>3$ modules, or integrates $>1$ external API).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Execution | System | Parses a Feature Spec and triggers `drafting/decomposition.py` | A `DecompositionPlan` object is produced containing component changes and integration seams. |
| FR-2 | Decision Gate | System | Presents the decomposition plan | A HITL gate waits for user approval/rejection. |
| FR-3 | Component Fan-out | System | Automatically spawns a sub-pipeline iteration (generate Component Spec) for each approved component | N individual L3 pipelines are launched (Multi-spec Pipeline Fan-out). |
| FR-4 | Quality Automation | System | Applies standard 10-test battery (Structure Tests 1-5 + Code Quality) against each Component Spec | The pipeline advances only if all gates pass. |
| FR-5 | Coverage Check | System | Verifies that the resulting combined components cover 100% of the Feature Spec's Blast Radius | Will signal ERROR or Loop Back if coverage is incomplete. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Resilience | 3-strikes loop rule on failures before hard aborting |
| NFR-2 | Interactivity | Must allow graceful HITL feedback injection for re-generation of rejected planes |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Tree-sitter | (Current) | Code Parsing | Yes | N/A |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Use Pipeline `auto` / `hitl` Gates | The flow engine already supports gating. We rely on standard `StepResult` / Gate configurations instead of a bespoke runner | No |
| AD-2 | Automated Recursive Spawn | `flow/runner.py` will allow a pipeline step to dynamically queue new L3 sub-pipelines | No |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Pipeline Multi-Spawning | How to write YAML pipelines that fan-out recursive sub-pipelines | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Hierarchical Orchestration Engine Support
- **Scope**: Implements multi-pipeline spawning / dynamic `fan_out` within `flow/runner.py` to allow triggering component pipelines programmatically from a Decomposition plan.
- **FRs**: [FR-1, FR-3]
- **Inputs**: A parsed `DecompositionPlan` and a target pipeline reference (e.g. `new_feature.yaml` or Component equivalent).
- **Outputs**: Dynamic pipeline executions logged in `flow.store`.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3_24/feature_3_24_sf1_implementation_plan.md

### SF-2: Verified Iterative Loop & Traceability Enforcement
- **Scope**: Implements the DMZ-style retry loop, HITL presentation integration, and Blast Radius coverage mapping (FR-5).
- **FRs**: [FR-2, FR-4, FR-5]
- **Inputs**: Generated component specs and the top-level Feature Spec.
- **Outputs**: Assertions mapping 100% coverage, loop control (3-strikes).
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/phase_3/feature_3_24/feature_3_24_sf2_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Hierarchical Orchestration Support | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-2 | Verified Iterative Loop | SF-1 | ✅ | ✅ | ✅ | ✅ | ⬜ |

## Session Handoff

**Current status**: SF-2 Pre-Commit COMPLETE. Ready for final Git Commit.
