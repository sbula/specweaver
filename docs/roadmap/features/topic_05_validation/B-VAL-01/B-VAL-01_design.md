# Design: AST Drift Detection & AI Root-Cause Analysis

- **Feature ID**: 3.14a
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_05_validation/B-VAL-01/B-VAL-01_design.md

## Feature Overview

Feature 3.14a adds deep, parser-backed drift detection to SpecWeaver. It leverages the Artifact
Lineage UUIDs established in Feature 3.14 to traverse the graph to the structured Plan JSON
generated during Phase 3.6. By extracting the AST of the running code and comparing it structurally
to this pure JSON representation of the spec's intent, it autonomously identifies human-introduced
implementation drift and coverage gaps. Additionally, it offers an opt-in mode to use LLMs to
pinpoint the root cause of any detected violations. It interacts with the existing validation
pipeline and the flow engine, and does NOT touch real-time background file watching. Key
constraints: The AST gap analysis must be fast (no LLM required for the core AST check) to keep the
feedback loop tight.

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
| FR-3 | Drift Detection | System | SHALL detect structural mutations in the AST compared to the baseline spec expectations | A list of drift findings is produced |
| FR-4 | Gap Analysis | System | SHALL evaluate coverage by verifying AST nodes corresponding to spec scenarios exist | Missing scenarios are reported as coverage gaps |
| FR-5 | Root-Cause Analysis | System | SHALL trigger LLM root-cause analysis on detected drift ONLY when `--analyze` is passed | Explains why the drift happened |
| FR-6 | Drift CLI | Developer | SHALL run `sw drift check <file> [--analyze]` | Initiates structural inspection pipeline |

**FR-2 (Baseline Fetch) is deleted, not lost.** It claimed the plan would be fetched "via the file's
lineage UUID". That never happens on this command: `--plan` is a **required** option on
`sw drift check`, the handler reads `step.params["plan_path"]`, and neither the handler nor the
detector touches lineage or a UUID. (It *is* implemented elsewhere — see the correction below.)

The descope was a decision already taken and recorded — `B-VAL-01_sf02_implementation_plan.md`
§Open Questions weighs `Code UUID -> Spec UUID -> Plan UUID` plus a `specs/*_plan.yaml` glob against
an explicit flag and recommends the flag: *"This keeps it 100% fast, avoids globbing, and is
explicit."* That is what shipped. **The decision simply never reached this table**, so the design
went on advertising a resolution path the CLI cannot take.

Row deleted per `TECH-046`'s precedent, and the same shape as `TECH-062`, with one difference worth
naming: there the mechanism was absent and undecided, here it was consciously traded away in the plan
and the design was left stale. A descope recorded in one document and not the other is invisible to
every gate — `check_fr_sweep.py` sees an uncited FR, never a contradicted one.

**FR-2's mechanism does exist in the repo — on another capability's command.** Corrected 2026-08-17,
same day, on reaching `B-VAL-02`: `assurance/validation/interfaces/cli_drift.py` holds
**`_resolve_plan_by_lineage`**, which reads the file's `# sw-artifact` uuid, looks up its `parent_id`
in `flow_artifact_events`, and matches that parent against each candidate plan's own uuid. That is
FR-2 as written, almost clause for clause.

It is wired to **`sw drift check-rot`**, which is `B-VAL-02`'s pre-commit interceptor, and to nothing
else — `_target_has_drifted` is its only caller. A second resolver, `_plan_declaring`, backs it up by
matching `expected_signatures` path text in three spellings.

So the accurate statement is narrower than "never built": **`sw drift check` cannot resolve a plan and
never tries**, because `--plan` is required and the handler reads `step.params["plan_path"]`. The row
is still correctly deleted from *this* capability — the behaviour it promised is not on this command —
but a reader should know the mechanism is fifty lines away in the same file, owned by `B-VAL-02`, and
that wiring it in is a small change rather than a build.

Recorded 2026-08-17 from `INT-US-10-SF01-MIG`. Remaining FRs renumbered nowhere: FR-1, FR-3..FR-6
keep their identifiers so existing citations and plans stay valid.

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

### SF-01: AST Drift & Coverage Engine
- **Scope**: Core pure-logic component combining AST parser with Spec rule comparative matching.
- **FRs**: [FR-1, FR-2, FR-3, FR-4]
- **Inputs**: Source code file path and its parent Spec constraints (via `models`).
- **Outputs**: Structured drift and coverage findings (no LLM involved).
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_05_validation/B-VAL-01/B-VAL-01_sf01_implementation_plan.md

### SF-02: Flow Integration & CLI (`sw drift`)
- **Scope**: Expose the detector to pipelines and the CLI, providing opt-in LLM root-cause pinpointing.
- **FRs**: [FR-5, FR-6]
- **Inputs**: User CLI arguments, findings from SF-01, and UUIDs from DB context.
- **Outputs**: Pipeline step execution, terminal rendering, and an LLM root-cause response if requested.
- **Depends on**: [SF-01]
- **Impl Plan**: docs/roadmap/features/topic_05_validation/B-VAL-01/B-VAL-01_sf02_implementation_plan.md

## Execution Order

1. SF-01 (no deps — start immediately)
2. SF-02 (depends on SF-01)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | AST Drift Engine | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Flow Integration & CLI | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Implementation Plan APPROVED for SF-02. Ready for Flow Validation & CLI development.
**Next step**: Run TDD workflow: `/dev docs/roadmap/features/topic_05_validation/B-VAL-01/B-VAL-01_sf02_implementation_plan.md`
