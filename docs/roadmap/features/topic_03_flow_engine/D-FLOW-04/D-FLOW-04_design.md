# D-FLOW-04 — Unified Runner Architecture & Universal Logging

**Status**: APPROVED · **COMPLETE** — SF-01, SF-02, SF-03 committed. · **Feature ID**: 3.13a ·
**Phase**: 3

| | |
|---|---|
| Changes | single-shot CLI commands (`sw review`, `sw draft`, `sw implement`) → 1-step `PipelineRunner` pipelines |
| Changes | `telemetry_logger.py`: Rich console + JSON file log |
| Touches | every module in `src/specweaver/` (logging rollout) |
| Not touched | multi-step YAML pipelines (NFR-1) |

## What it does

1. **One execution path.** Single-shot CLI commands run as dynamic 1-step pipelines through
   `PipelineRunner`, so telemetry, state tracking and execution are the same for every CLI operation.
2. **Logging reform.** Console: `rich.logging.RichHandler`, colorized, WARNING+. Disk: a JSON-formatted
   `RotatingFileHandler` with DEBUG logs for post-mortem debugging.
3. **Logging rollout.** Structured log calls in every module, class and public method.

## Why this way

- Before: commands such as `sw review` built their domain objects (e.g., `Reviewer`) by hand and
  flushed telemetry by hand. `PipelineRunner` already handles telemetry, database contexts and gates
  for multi-step pipelines; reusing it for 1-step definitions adds no new pattern.
- `telemetry_logger.py` used a plain `StreamHandler` on the console, not `Rich`. `RichHandler` plugs
  into stdlib logging, so no new dependency. Standard CLI pattern: a rich
  console UI, plus parseable logs for telemetry/server backends.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | CLI delegates to Flow Handler | CLI commands use `PipelineRunner`, which relies on Handlers (`_review.py`, `_draft.py`), instead of instantiating `Reviewer` directly. Cuts direct coupling of the CLI module (`cli/` consuming `review/`, `drafting/`) by enforcing the `PipelineRunner` boundary. | No |
| AD-2 | Python `logging` over `structlog` | The project already uses `Rich` extensively. `RichHandler` integrates with Python standard logging without new dependencies: minimal disruption, visual cohesion. | No |
| AD-3 | Incremental logging rollout by layer | Rollout grouped by architectural layer (config → core domain → flow → llm → cli → api) to stay testable at each stage. Pure data models and `__init__.py` files are excluded. | No |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Refactor CLI commands | System | Refactor single-shot CLI commands (`sw draft`, `sw review`, etc.) to execute via `PipelineRunner` | Commands use dynamic 1-step pipelines instead of manual domain instantiation. |
| FR-2 | Introduce Rich Console Logging | System | Replace `StreamHandler` in `src/specweaver/telemetry_logger.py` with `rich.logging.RichHandler` | The console outputs formatted, colorized WARNING+ level messages with rich tracebacks. |
| FR-3 | Implement Persistent JSON Logs | System | Add a JSON formatter to the `RotatingFileHandler` writing to `~/.specweaver/logs/<project_name>/specweaver.log` | DEBUG and higher logs are captured on disk in a machine-parseable JSON format without spamming the terminal. |
| FR-4 | Preserve Existing CLI Contracts | User | Call existing `sw` CLI commands with their current flags | The UI arguments and flags remain functionally identical. |
| FR-5 | Automatic Telemetry & Context | System | Delegate context resolution and telemetry flushing to `PipelineRunner` | The manual cleanup in CLI command modules is removed in favor of the unified runner hooks. |
| FR-6 | Logging Rollout | System | Add structured `logger.debug`/`info`/`warning`/`error` calls to every module, class, and public method across the codebase | Every module has a module-level `logger = logging.getLogger(__name__)` and every public method/function emits at least entry-level debug logs and error-path warning/error logs. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Backward Compatibility | `PipelineRunner` changes MUST NOT break existing multi-step YAML pipelines. |
| NFR-2 | Console Cleanliness | Debug logs MUST NOT be shown on the console unless `--debug` is explicitly passed. Default terminal log verbosity remains WARNING+. |
| NFR-3 | Consistent Logging Pattern | All modules MUST use `logger = logging.getLogger(__name__)` at module level. Log messages MUST use lazy formatting (`logger.debug("msg %s", val)`) not f-strings. |

## Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Python `logging` | stdlib | `getLogger`, `RotatingFileHandler` | Yes | Built-in |
| Rich | >=13.0.0 | `rich.logging.RichHandler` | Yes | Provided via `typer[all]` (`pyproject.toml`) |

## Sub-features

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-01 | Universal Logging Reform: `telemetry_logger.py` sends terminal output through `Rich` and disk output as JSON. | FR-2, FR-3 | logger configuration requests from CLI/System → formatted console strings, JSON file lines | none | [sf01](D-FLOW-04_sf01_implementation_plan.md) |
| SF-02 | Unified CLI Runner: single-shot commands (`sw review`, `sw draft`, etc.) run as programmatic 1-step pipelines via `PipelineRunner`. | FR-1, FR-4, FR-5 | CLI arguments, current project context → module runs through the `flow/` engine, telemetry flushed | none | [sf02](D-FLOW-04_sf02_implementation_plan.md) |
| SF-03 | Logging Rollout: `logger.debug`, `logger.info`, `logger.warning`, `logger.error` calls across all of `src/specweaver/`; every module declares `logger = logging.getLogger(__name__)`; every public function/method logs at least entry (debug) and error paths. | FR-6 | existing module source + SF-01 infrastructure → all modules instrumented | SF-01 | [sf03](D-FLOW-04_sf03_implementation_plan.md) |

SF-01 and SF-02 share no functional dependency and could run in parallel; SF-03 needs SF-01 first and
could run in parallel with SF-02.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Universal Logging Reform | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Unified CLI Runner | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Logging Rollout | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
