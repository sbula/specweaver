# C-VAL-04 — Automated Traceability Matrix

**Status**: APPROVED · **COMPLETE** — SF-01 committed. · **Feature ID**: 3.21 · **Phase**: 3

| | |
|---|---|
| Adds | code rule `C09: Traceability` (after `c01`–`c08`) |
| Uses | the Markdown spec parser, `tree-sitter` AST extraction, the validation pipelines |
| Not touched | execution logic, runtime behavior; test *quality* (`A-VAL-03`, mutation) |

## What it does

Detects **omissions**: requirements no test claims at all. It counts the Functional and
Non-Functional Requirements in the L3 Spec and asserts a matching `@traces(req_id)` tag for each one
in the AST of the generated test files. Missing coverage hard-fails the validation pipeline.

It does **not** catch correlated hallucinations: the tag is written by the same LLM as the test, so a
hallucinated test carries a well-formed tag. *(Corrected 2026-08-20 — the design first claimed it
did.)* Test quality is `A-VAL-03`'s territory; see `docs/analysis/benefit_chain_analysis_2026-08-20.md`.

## Why this way

- **Structural AST parsing, not text search** — reuses the `tree-sitter` stack already behind
  `standards/tree_sitter_base.py` and AST drift detection (`validation/drift_detector.py`).
- **A code rule** in `validation/rules/` (SpecWeaver's 10-test battery, 8 code rules at design time),
  wired into `pipelines/validation_code_default.yaml` and the domain profiles.
- **Boundaries**: lives in `validation` (pure-logic archetype), imports nothing from `loom/*`; a static
  post-generation check only.

Blueprint: `ORIGINS.md`, the HEPH / agent-system verification section (Spec-Traceable Scenario
Testing, Requirement Traceability).

**Since moved:** the rule lives in `src/specweaver/assurance/validation/rules/code/`; the pipeline in
`src/specweaver/workflows/pipelines/`.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Create `c09_traceability.py` rule | Best fit for static code-quality assertions post-generation. | No |
| AD-2 | Extend `ValidationRunner` context with parsed FRs | The FRs must be parsed and passed down to code validation tasks to keep validation stateless. | No |
| AD-3 | Option 1: Zero-Dependency Meta-Comments for Tracing | Traces are code comments (e.g., `# @trace(FR-x)`) parsed via `tree-sitter`. No external or language-side dependency; honors the polyglot Black Box constraint. | Yes - Approved by user on 2026-04-06 |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | System | Count Spec Req. | Parse and enumerate all Functional Requirements (FRs) and Non-Functional Requirements (NFRs) in the target L3 spec. | Returns a definitive list of required `req_id`s. |
| FR-2 | System | Extract Test Tags | Parse the AST of all generated test files to locate all `@traces(req_id)` annotations/decorators attached to test functions. | Returns a set of `req_id`s actually covered by the tests. |
| FR-3 | System | Verify Coverage | Match the extracted `req_id` tags from the AST against the full list of parsed FRs/NFRs from the spec. | Coverage metrics showing completeness or missing reqs. |
| FR-4 | System | Enforce Validation | Hard-fail the pipeline if any FR/NFR from the spec lacks a corresponding `@traces` tag in the test AST. | Pipeline emits ERROR findings and halts. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Accuracy | 100% exact string match required between spec requirement IDs and AST extracted IDs. |
| NFR-2 | AST Enforcement | Must use structural AST traversal (`tree-sitter`) targeting comments, avoiding regex on raw text. |

## Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| `tree-sitter` | Current (as in `pyproject.toml`) | `Language`, `Parser`, `Query` | Yes | Existing dependency |

## Guides owed

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Developer Traceability | How TDD tasks must include zero-dependency `# @trace("FR-X")` comments directly above tests for a successful commit. | ⬜ To be written during Pre-commit |

## Sub-features

Single feature — no decomposition.

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-01 | Traceability Validation Engine: spec parsing for FR/NFRs, AST extraction of `@traces` from test files, the code-rule pipeline hook that enforces coverage. | FR-1, FR-2, FR-3, FR-4 | L3 Spec text/file path + generated test files → Validation RuleResult (Pass/Fail) with `DriftFinding` metrics | none | [plan](C-VAL-04_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Traceability Validation Engine | — | ✅ | ✅ | ✅ | ✅ | ✅ |
