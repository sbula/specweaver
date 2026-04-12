# Design: Automated Traceability Matrix

- **Feature ID**: 3.21
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3_21/feature_3_21_design.md

## Feature Overview

Feature 3.21 adds an Automated Traceability Matrix (`@traces`) to the validation layer. It solves "Correlated Hallucinations" (where tests pass but don't map to actual requirements) by mathematically counting Functional and Non-Functional Requirements in the L3 Spec and asserting exact matching `@traces(req_id)` tags in the AST of generated test files. It interacts natively with the Markdown spec parser, AST extraction tools, and validation pipelines, and does NOT touch execution logic or runtime behavior.
Key constraints: Hard-fails the validation pipeline if coverage is incomplete. Must use structural AST parsing instead of naive text search.

## Research Findings

### Codebase Patterns
- **AST Parsing**: The codebase already leverages `tree-sitter` for `standards/tree_sitter_base.py` and AST drift detection (`validation/drift_detector.py`). The existing architecture can be cleanly reused to extract decorators/tags from Python test files.
- **Validation Engine**: SpecWeaver's 10-test battery resides in `validation/rules/`. There are currently 8 code rules (`c01`–`c08`). This feature perfectly aligns with creating `C09: Traceability`, checking test coverage against spec requirements via AST extraction.
- **Pipelines**: The new rule will be integrated directly into `pipelines/validation_code_default.yaml` and appropriate domain profiles.
- **Boundaries**: Must reside within `validation` (pure-logic archetype) without importing from `loom/*`. The feature acts purely as a static post-generation verification step.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| `tree-sitter` | As in `pyproject.toml` | Parsing Python test files for `@traces` tags | Already used natively within `validation/` |

### Blueprint References
- See `ORIGINS.md` section on HEPH and agent-system verification (Spec-Traceable Scenario Testing, Requirement Traceability).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | System | Count Spec Req. | Parse and enumerate all identifiable Functional Requirements (FRs) and Non-Functional Requirements (NFRs) documented in the target L3 spec. | Returns a definitive list of required `req_id`s. |
| FR-2 | System | Extract Test Tags | Parse the AST of all generated test files using native tools to locate all `@traces(req_id)` annotations/decorators attached to test functions. | Returns a set of `req_id`s actually covered by the tests. |
| FR-3 | System | Verify Coverage | Match the extracted `req_id` tags from the AST against the full list of parsed FRs/NFRs from the spec. | Computation of coverage metrics indicating completeness or missing reqs. |
| FR-4 | System | Enforce Validation | Hard-fail the pipeline execution if any identified FR/NFR from the spec lacks a corresponding `@traces` tag in the test AST. | Pipeline emits ERROR findings and halts. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Accuracy | 100% exact string match required between spec requirement IDs and AST extracted IDs. |
| NFR-2 | AST Enforcement | Must use structural AST traversal (`tree-sitter`) targeting comments, avoiding regex on raw text. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| `tree-sitter` | Current | `Language`, `Parser`, `Query` | Yes | Existing dependency |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Create `c09_traceability.py` rule | Best fit for static code quality assertions post-generation. | No |
| AD-2 | Extend `ValidationRunner` context with parsed FRs | The FRs must be parsed and passed down to code validation tasks to maintain statelessness of validation. | No |
| AD-3 | Option 1: Zero-Dependency Meta-Comments for Tracing | Traces will be placed in code comments (e.g., `# @trace(FR-x)`) parsed natively via `tree-sitter`. Requires no external or language-side dependencies and strictly honors the polyglot Black Box constraint. | Yes - Approved by user on 2026-04-06 |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Developer Traceability | Document how TDD tasks must include zero-dependency `# @trace("FR-X")` comments directly above tests for successful commit. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

Single feature — no decomposition.

### SF-1: Traceability Validation Engine
- **Scope**: Implements spec parsing for FR/NFRs, AST extraction of `@traces` from test files, and the code rule pipeline hook to enforce coverage.
- **FRs**: [FR-1, FR-2, FR-3, FR-4]
- **Inputs**: The L3 Spec text/file path, and generated test files.
- **Outputs**: Validation RuleResult (Pass/Fail) with `DriftFinding` metrics.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3_21/feature_3_21_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Traceability Validation Engine | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Implementation Plan APPROVED.
**Next step**: Run:
`/dev docs/roadmap/phase_3/feature_3_21/feature_3_21_implementation_plan.md SF-1`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
