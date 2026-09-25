# D-VAL-04 — Adaptive Assurance Standards

**Status**: APPROVED. **COMPLETE** — SF-01 and SF-02 merged. · **Feature ID**: 3.32a · **Phase**: 3

| | |
|---|---|
| Extends | `StandardsAnalyzer` / `StandardsScanner` (`assurance/standards`) |
| Touches | `specweaver.toml` config parsing · `PromptBuilder` context injection |
| Reuses | `tree-sitter` bindings (`commons/language/ast_parser.py`) |
| Blueprint | Feature 3.32d Refactoring Design (Phase 3 Optimizations), `docs/architecture/feature_3_32d_refactoring_design.md` — AST Skeleton Condensation (1.1) |

## What it does

Adds two standards modes to `StandardsAnalyzer`: **Mimicry** (extract conventions from the repo) and
**Best Practice** (use built-in idiomatic targets). A greenfield repo has no code to extract from —
the "Empty Repository" vacuum — so Best Practice falls back to built-in defaults instead of failing.

It also condenses injected context: dependency files go into the prompt as deterministic AST
skeletons (signatures) instead of raw file content, which cuts tokens and speeds context resolution.

## Why this way

`StandardsAnalyzer` extracts naming and architecture constraints by AST across all scopes, so it
expects existing code. Built-in profiles need a second logic layer inside `assurance/standards`; the
`tree-sitter` bindings are reused. Skeletons were chosen from the Phase 3 optimizations review as
the
highest-return change for standards injection.

Constraints: follow every `.yaml` context (`context.yaml` `forbids`); no architectural boundary
violations.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Scaffold Config Defaults via Database | No generic default AST logic in code; uses the `config` layer's pure-logic mapping. | No |
| AD-2 | AST Skeleton Condensation Injection | Replaces appending whole files to the context window with deterministic signature indexing at the compiler boundaries. Lowers token cost. | No |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse configurable standard targets | System | Reads `specweaver.toml` | Returns targeted mode ("mimicry" vs "best_practice") |
| FR-2 | Fallback to Built-in Context | StandardsAnalyzer | Detects "best_practice" mode | Injects scaffolding configuration defaults mapped from `context.db` profiles without executing `loom` execution tools |
| FR-3 | Condense Context via Skeletons | PromptBuilder | Modifies injected metadata | Redundant context data is truncated into deterministic AST Skeletons |
| FR-4 | Implement Safe Graph Referencing | TopologyGraph | Reads file topologies | Executes dependency bounds referencing without reloading files, to improve cycle speeds |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Boundary Compliance | `StandardsAnalyzer` must never invoke `loom/*` tools per `context.yaml` `forbids` rules. **[proof: arch — tach/lint gate, not pytest]** |
| NFR-2 | Performance ROI | System must achieve token size reductions without decreasing accuracy. **[proof: none — unfalsifiable as written]** |

## External dependencies

| Tool | Version | Key API Surface | Source | Compat Confirmed |
|------|---------|----------------|--------|-----------------|
| tree-sitter | * (min: N/A) | AST extraction / parsing syntax | `commons/language` | Y — already integrated |

## Guides owed

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Adding Built-in Standards | How to contribute idiomatic standards for new languages. | ⬜ To be written during Pre-commit |

## Sub-features

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-01 | Mode toggle in `StandardsAnalyzer` + config parsing for "mimicry" vs "best_practice"; maps historical `context.db` defaults. | FR-1, FR-2 | `specweaver.toml` settings, greenfield target paths → resolved built-in standard rule payloads | none | [sf01](D-VAL-04_sf01_implementation_plan.md) |
| SF-02 | AST skeletons in the context layer to limit token payload size. | FR-3, FR-4 | topological structure of source dependencies → truncated prompts carrying the same semantic data | SF-01 | [sf02](D-VAL-04_sf02_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Adaptive Standard Configurations | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Context Condensation Skeletons | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
