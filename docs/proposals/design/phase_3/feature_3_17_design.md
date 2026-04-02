# Design: Spec-to-Code Traceability (Artifact Lineage)

- **Feature ID**: 3.14
- **Phase**: 3
- **Status**: COMPLETE
- **Design Doc**: docs/proposals/design/phase_3/feature_3_17_design.md

## Feature Overview

Feature 3.14 adds structural Spec-to-Code Traceability (Artifact Lineage) to the pipeline runner.
It solves the credit assignment and traceability problem by recording a directional lineage graph (Spec → Plan → Code) in the SQLite database, tagging each artifact with a UUID, parent UUID, and generating LLM model.
It interacts with the `PipelineRunner`, DB telemetry layer, and code generators, and does NOT touch AST-based drift detection, coverage gap detection, or AI-powered root-cause analysis.
Key constraints: Minimal code pollution (one `# sw-artifact: <uuid>` tag per file), robust against manual file renames, and includes rapid orphan detection via CLI.

## Research Findings

### Codebase Patterns
- Currently, `PipelineRunner` (`flow/runner.py`) handles all executions and emits state changes.
- Telemetry logs to `llm_usage_log` via `config/_db_telemetry_mixin.py`. The lineage graph is a natural extension of this telemetry and belongs in `specweaver.db`.
- Code generation is orchestrated by `flow/_generation.py` using `CodeGenerator`.
- The CLI commands live in `cli/`, which forbids raw I/O (`loom/*`). Static file reads must be done using pure `pathlib` (e.g. `graph/lineage.py`).
- UUID injection into files should be handled deterministically by the LLM (via `PromptBuilder` instructions) to respect comment syntax, rather than post-generation text manipulation by the engine.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| sqlite3 | built-in | `INSERT`, `SELECT` for graph edges | standard lib |
| uuid | built-in | `uuid.uuid4()` | standard lib |

### Blueprint References
- `future_capabilities_reference.md` §17 (Spec-to-Code Traceability)
- `llm_routing_and_cost_analysis.md` (Artifact Lineage Graph)

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | DB Storage | System | SHALL record a lineage graph for generated artifacts linking each child to its parent | Graph is persisted in `specweaver.db` |
| FR-2 | UUID Tagging | LLM/Engine | SHALL inject a single `# sw-artifact: <uuid>` tag into every generated file on disk | Every generated file carries its UUID |
| FR-3 | Graph Metadata | System | SHALL persist `artifact_id`, `parent_id`, `model_id`, timestamp, and `run_id` | Full provenance tracking enabled |
| FR-4 | Trace CLI | Developer | SHALL view lineage history of a file using `sw lineage <file>` | CLI prints tree from DB |
| FR-5 | Orphan CLI | CI/Dev | SHALL run `sw check --lineage` | Fails if untracked manual code is detected in `src/` |
| FR-6 | Manual Tag CLI | Developer | SHALL run `sw lineage tag <file> --author human` | Injects UUID tag and logs provenance with `model_id=human` in DB |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | `sw check --lineage` scans 100 files in < 500ms |
| NFR-2 | DB Compatibility | Schema migration must be additive, no break of `llm_usage_log` |
| NFR-3 | Resilience | Manual file renaming must not break the lineage graph (rely on tags in content, not paths) |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| sqlite3 | (python built-in) | DB I/O | Yes | We already use this extensively |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Lineage graph stored in `specweaver.db` | Logically related to telemetry, ensures cost analytics can seamlessly JOIN usage and provenance. | No |
| AD-2 | UUID generation in `flow/` | The Runner knows the lineage context (which step is running, what the parent spec is). | No |
| AD-3 | Rely on LLMs to write `# sw-artifact` | Safer than having engine heuristically mutate LLM output (avoids syntax corruption in JSON/YAML/Python). | No |
| AD-4 | `sw check --lineage` uses pure `pathlib` | Required because `cli` forbids `loom/*`. Same pattern as `standards` auto-discovery. | No |
| AD-5 | Pass UUID via PipelineRun StepRecords | State must explicitly track `artifact_uuid` per step so downstream steps can look up their parent UUID deterministically. | No |

## Sub-Feature Breakdown

### SF-1: Lineage Database & Flow Integration
- **Scope**: Implements the SQLite persistence and UUID context propagation within the PipelineRunner.
- **FRs**: [FR-1, FR-3]
- **Inputs**: Current `run_id` and pipeline definition context (parent artifact DB).
- **Outputs**: UUIDs passed down to handlers; DB rows persisted in `lineage_graph`.
- **Depends on**: none
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_17_sf1_implementation_plan.md

### SF-2: Artifact Tagging Engine
- **Scope**: Injects instructions into LLM prompts via `PromptBuilder` to write UUID tags and coordinates generation handlers to bind `parent_uuid` to `artifact_uuid`.
- **FRs**: [FR-2]
- **Inputs**: Generated UUIDs from SF-1.
- **Outputs**: Generated code on disk containing `# sw-artifact: <uuid>`.
- **Depends on**: SF-1
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_17_sf2_implementation_plan.md

### SF-3: Verification & CLI Tools
- **Scope**: Implements orphan detection, manual tagging, and lineage tracing CLI commands.
- **FRs**: [FR-4, FR-5, FR-6]
- **Inputs**: `pathlib` scans of `src/` and SQLite SELECT queries.
- **Outputs**: Terminal output and exit codes for CI.
- **Depends on**: SF-1, SF-2
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_17_sf3_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)
3. SF-3 (depends on SF-2)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | DB & Flow | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Tagging | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | Verification CLI | SF-2 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Feature complete. Ready for dogfood + merge.
**Next step**: Move to Feature 3.15 (Automated iterative decomposition).
