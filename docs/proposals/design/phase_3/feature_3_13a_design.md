# Design: Unified Runner Architecture & Universal Logging

- **Feature ID**: 3.13a
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/design/phase_3/feature_3_13a_design.md

## Feature Overview

Feature 3.13a adds a unified execution flow to single-shot CLI commands (`sw review`, `sw draft`, `sw implement`) by refactoring them to use dynamic 1-step pipelines via `PipelineRunner`. It solves execution inconsistency by standardizing telemetry, state tracking, and execution paths across all CLI operations. As part of this, it conducts a project-wide logging reform by introducing `rich.logging.RichHandler` for colorized console output and a JSON-formatted `RotatingFileHandler` for persistent DEBUG logging. Finally, it rolls out structured logging calls across every module in the codebase, ensuring every class and public method emits appropriate log messages for observability and post-mortem debugging.

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
| FR-6 | Logging Rollout | System | Add structured `logger.debug`/`info`/`warning`/`error` calls to every module, class, and public method across the codebase | Every module has a module-level `logger = logging.getLogger(__name__)` and every public method/function emits at least entry-level debug logs and error-path warning/error logs. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Backward Compatibility | `PipelineRunner` changes MUST NOT break existing multi-step YAML pipelines. |
| NFR-2 | Console Cleanliness | Debug logs MUST NOT be shown on the console unless `--debug` is explicitly passed. Default terminal log verbosity remains WARNING+. |
| NFR-3 | Consistent Logging Pattern | All modules MUST use `logger = logging.getLogger(__name__)` at module level. Log messages MUST use lazy formatting (`logger.debug("msg %s", val)`) not f-strings. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Rich | >=13.0.0 | `rich.logging.RichHandler` | Yes | Provided via `typer[all]` |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | CLI delegates to Flow Handler | CLI commands should use `PipelineRunner` which relies on Handlers (`_review.py`, `_draft.py`) instead of instantiating `Reviewer` directly. | Decreases direct-coupling of the CLI module (`cli/` consuming `review/`, `drafting/`) to enforcing the `PipelineRunner` boundary. | No |
| AD-2 | Python `logging` over `structlog` | The project already uses `Rich` extensively. `RichHandler` integrates cleanly with Python standard logging without introducing new dependencies. | Minimal disruption, maximum visual cohesion. | No |
| AD-3 | Incremental logging rollout by layer | Rollout is grouped by architectural layer (config → core domain → flow → llm → cli → api) to maintain testability at each stage. Pure data models and `__init__.py` files are excluded. | No |

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

### SF-3: Logging Rollout
- **Scope**: Add structured logging calls (`logger.debug`, `logger.info`, `logger.warning`, `logger.error`) to every module, class, and public method across the entire `src/specweaver/` tree. Ensure every module declares `logger = logging.getLogger(__name__)` and every public function/method emits at least method-entry debug logs and error-path logs.
- **FRs**: [FR-6]
- **Inputs**: Existing module source code, logging infrastructure from SF-1.
- **Outputs**: All modules instrumented with structured logging calls.
- **Depends on**: SF-1 (logging infrastructure must be in place)
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_13a_sf3_implementation_plan.md

## Execution Order

1. SF-1 and SF-2 can be executed in parallel (both have no shared functional dependencies).
2. SF-3 depends on SF-1 (must complete first). SF-3 can run in parallel with SF-2.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Universal Logging Reform | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Unified CLI Runner | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-3 | Logging Rollout | SF-1 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-1 Committed. SF-2 Impl Plan approved, Dev pending. SF-3 Impl Plan APPROVED.
**Next step**: Run `/dev docs/proposals/roadmap/phase_3/feature_3_13a_sf3_implementation_plan.md` to implement SF-3.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
