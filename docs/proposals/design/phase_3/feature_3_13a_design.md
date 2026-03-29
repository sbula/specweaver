# Design: Unified Runner Architecture & Universal Logging

- **Feature ID**: 3.13a
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/design/phase_3/feature_3_13a_design.md

## Feature Overview

Feature 3.13a adds a unified execution flow to single-shot CLI commands (`sw review`, `sw draft`, `sw implement`) by refactoring them to use dynamic 1-step pipelines via `PipelineRunner`. It solves execution inconsistency by standardizing telemetry, state tracking, and execution paths across all CLI operations. As part of this, it conducts a project-wide logging reform by introducing `rich.logging.RichHandler` for colorized console output and a JSON-formatted `RotatingFileHandler` for persistent DEBUG logging.

## Research Findings

### Codebase Patterns
Existing CLI commands such as `sw review` manually instantiate their backing domain objects (e.g., `Reviewer`) and manually trigger telemetry flushing. The `PipelineRunner` successfully orchestrates multi-step pipelines and robustly manages telemetry, database contexts, and gates automatically. Reusing `PipelineRunner` for single-step programmatic definitions unifies these paths without creating new architectural patterns. The existing `logging.py` uses standard library Python logging but defaults the console to a plain `StreamHandler` rather than integrating with `Rich`. 

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Python `logging` | stdlib | `getLogger`, `RotatingFileHandler` | Built-in |
| Rich `RichHandler` | >=13.0 | `rich.logging.RichHandler` | `pyproject.toml` (via `typer[all]`) |

### Blueprint References
No external blueprint references are strictly required, though this follows the standard CLI pattern of rich console UIs while preserving parseable logs for telemetry/server backends.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Refactor CLI commands | System | Refactor single-shot CLI commands (`sw draft`, `sw review`, etc.) to execute via `PipelineRunner` | Commands use dynamic 1-step pipelines instead of manual domain instantiation. |
| FR-2 | Introduce Rich Console Logging | System | Replace `StreamHandler` in `src/specweaver/logging.py` with `rich.logging.RichHandler` | The console outputs properly formatted, colorized WARNING+ level messages with rich tracebacks. |
| FR-3 | Implement Persistent JSON Logs | System | Add a JSON formatter to the `RotatingFileHandler` writing to `~/.specweaver/logs/<project_name>/specweaver.log` | DEBUG and higher logs are persistently captured in a machine-parseable JSON format without spamming the terminal user. |
| FR-4 | Preserve Existing CLI Contracts | User | Call existing `sw` CLI commands with their current flags | The UI arguments and flags remain functionally identical. |
| FR-5 | Automatic Telemetry & Context | System | Delegate context resolution and telemetry flushing to `PipelineRunner` | The manual cleanup in CLI command modules is removed in favor of the unified runner hooks. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Backward Compatibility | `PipelineRunner` changes MUST NOT break existing multi-step YAML pipelines. |
| NFR-2 | Console Cleanliness | Debug logs MUST NOT be shown on the console unless `--debug` is explicitly passed. Default terminal log verbosity remains WARNING+. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Rich | >=13.0.0 | `rich.logging.RichHandler` | Yes | Provided via `typer[all]` |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | CLI delegates to Flow Handler | CLI commands should use `PipelineRunner` which relies on Handlers (`_review.py`, `_draft.py`) instead of instantiating `Reviewer` directly. | Decreases direct-coupling of the CLI module (`cli/` consuming `review/`, `drafting/`) to enforcing the `PipelineRunner` boundary. | No |
| AD-2 | Python `logging` over `structlog` | The project already uses `Rich` extensively. `RichHandler` integrates cleanly with Python standard logging without introducing new dependencies. | Minimal disruption, maximum visual cohesion. | No |

## Sub-Feature Breakdown

### SF-1: Universal Logging Reform
- **Scope**: Reform the `logging.py` infrastructure to unify terminal output via `Rich` and disk output via simple JSON representation.
- **FRs**: [FR-2, FR-3]
- **Inputs**: Logger configuration requests from CLI/System.
- **Outputs**: Formatted console strings, JSON file lines.
- **Depends on**: none
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_13a_sf1_implementation_plan.md

### SF-2: Unified CLI Runner
- **Scope**: Refactor single-shot CLI commands (`sw review`, `sw draft`, etc.) to execute via programmatic dynamic 1-step pipelines using `PipelineRunner`.
- **FRs**: [FR-1, FR-4, FR-5]
- **Inputs**: CLI command arguments, current project context.
- **Outputs**: Validated module executions natively integrated with `flow/` engine, telemetry flushed.
- **Depends on**: none
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_13a_sf2_implementation_plan.md

## Execution Order

1. SF-1 and SF-2 can be executed in parallel (both have no shared functional dependencies).

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Universal Logging Reform | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Unified CLI Runner | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-1 Committed. SF-2 Impl Plan PENDING.
**Next step**: Run `/implementation-plan docs/proposals/design/phase_3/feature_3_13a_design.md SF-2` to audit and approve the SF-2 implementation plan.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
