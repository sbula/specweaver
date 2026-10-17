# D-FLOW-04 — Unified Runner Architecture & Universal Logging

**Status**: APPROVED by the user 2026-10-17 — reopened that day by the done-audit (FR-6 never held);
SF-04 built, and D-FLOW-04 signed off `✅` by the user 2026-10-17. · **Feature ID**: 3.13a · **Phase**: 3

| | |
|---|---|
| Changes | single-shot CLI commands (`sw review`, `sw draft`, `sw implement`) → 1-step `PipelineRunner` pipelines |
| Changes | `telemetry_logger.py`: Rich console + JSON file log |
| Touches | every `except` in `src/specweaver/` (SF-04) · the commit gate (a new check) |
| Not touched | multi-step YAML pipelines (NFR-1) |

## What it does

1. **One execution path.** Single-shot CLI commands run as dynamic 1-step pipelines through
   `PipelineRunner`, so telemetry, state tracking and execution are the same for every CLI operation.
2. **Logging reform.** Console: `rich.logging.RichHandler`, colorized, WARNING+. Disk: a JSON-formatted
   `RotatingFileHandler` with DEBUG logs for post-mortem debugging.
3. **No error is lost.** Every caught error is logged, raised, used, or given its reason — checked at every
   commit, so it holds in the future too `[agreed 2026-10-17]`.
4. **Levels are settings.** What reaches the console and what reaches the file are project settings, not
   code `[agreed 2026-10-17]`.

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
| FR-1 | Refactor CLI commands | System | Refactor single-shot CLI commands (`sw draft`, `sw review`, etc.) to execute via `PipelineRunner` | Commands run as dynamic pipelines through `PipelineRunner` instead of manual domain instantiation; "1-step" dropped, as `sw draft` runs draft, validate and review `[agreed 2026-10-17]` |
| FR-2 | Introduce Rich Console Logging | System | Replace `StreamHandler` in `src/specweaver/telemetry_logger.py` with `rich.logging.RichHandler` | The console outputs formatted, colorized WARNING+ level messages with rich tracebacks. |
| FR-3 | Implement Persistent JSON Logs | System | Add a JSON formatter to the `RotatingFileHandler` writing to `~/.specweaver/logs/<project_name>/specweaver.log` | DEBUG and higher logs are captured on disk in a machine-parseable JSON format without spamming the terminal. |
| FR-4 | Preserve Existing CLI Contracts | User | Call existing `sw` CLI commands with their current flags | The UI arguments and flags remain functionally identical — a recorded list of every command's flags fails any test run that removes, renames or adds one unrecorded `[agreed 2026-10-17]` |
| FR-6 | No error is lost | Every `except` in `src/specweaver/` | SHALL log the error, raise, use the caught error, or carry `# expected: <why>` on its line; a check in the commit gate fails any other, with no baseline — every offender is fixed `[agreed 2026-10-17]` (measured: 116; the other 93 of the 209 that neither log nor raise use their error) | a swallowed failure always leaves a trace or a stated reason |
| FR-7 | Levels are settings | `sw config set-log-level` | SHALL set the file level (default DEBUG) and, with `--console`, the console level (default WARNING), per project `[agreed 2026-10-17]` | what the console and the file show is chosen, not coded |
| FR-8 | The level of a caught error | Every log line FR-6 adds | SHALL be DEBUG, or WARNING when the lost error changes what the user gets — a test result, a report, a file `[agreed 2026-10-17]` | a console warning still means *look here* |

| FR-9 | Every log line reaches its handlers | Every module in `src/specweaver/` | SHALL log through `logging.getLogger(__name__)` only and never `print()`; ruff `T20` and a check in the commit gate refuse both `[agreed 2026-10-17]` | a future module's lines reach the project's console and file, at their levels |

FR-5 (*the runner flushes telemetry, so commands do no manual cleanup*) is deleted: since `C-FLOW-01`
the collector writes each call itself, and `C-FLOW-01` FR-4 states and proves that one writer
`[agreed 2026-10-17]`.

FR-6 replaces the rollout as first written — a logger in every module and an entry line in every public
function. That part is descoped: it adds noise, not facts `[agreed 2026-10-17]`.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Backward Compatibility | `PipelineRunner` changes MUST NOT break existing multi-step YAML pipelines. |
| NFR-2 | Console Cleanliness | The console shows what the project's console level allows; the default is WARNING+. (The `--debug` flag first named here never existed; FR-7 replaces it `[agreed 2026-10-17]`.) |
| NFR-3 | Consistent Logging Pattern | A module that logs uses `logger = logging.getLogger(__name__)`. Log messages use lazy formatting (`logger.debug("msg %s", val)`), never f-strings — ruff rule `G004` in the commit gate `[agreed 2026-10-17]`. |

## Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Python `logging` | stdlib | `getLogger`, `RotatingFileHandler` | Yes | Built-in |
| Rich | >=13.0.0 | `rich.logging.RichHandler` | Yes | Provided via `typer[all]` (`pyproject.toml`) |

## Sub-features

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-01 | Universal Logging Reform: `telemetry_logger.py` sends terminal output through `Rich` and disk output as JSON. | FR-2, FR-3 | logger configuration requests from CLI/System → formatted console strings, JSON file lines | none | [sf01](D-FLOW-04_sf01_implementation_plan.md) |
| SF-02 | Unified CLI Runner: single-shot commands (`sw review`, `sw draft`, etc.) run as programmatic pipelines via `PipelineRunner`. | FR-1, FR-4 | CLI arguments, current project context → module runs through the `flow/` engine, telemetry flushed | none | [sf02](D-FLOW-04_sf02_implementation_plan.md) |
| SF-03 | Logging Rollout: `logger.debug`, `logger.info`, `logger.warning`, `logger.error` calls across all of `src/specweaver/`; every module declares `logger = logging.getLogger(__name__)`; every public function/method logs at least entry (debug) and error paths. | FR-6 | existing module source + SF-01 infrastructure → all modules instrumented | SF-01 | [sf03](D-FLOW-04_sf03_implementation_plan.md) |

| SF-04 | No error is lost: the check in the commit gate, `G004`, every `except` fixed module by module; the console level as a setting; every logger reaches its handlers; the flag contract | FR-4, FR-6, FR-7, FR-8, FR-9, NFR-2, NFR-3 | every `except` → logged, raised, used or reasoned; `sw config set-log-level --console` | SF-01 | — |

SF-01 and SF-02 share no functional dependency and could run in parallel; SF-03 needs SF-01 first and
could run in parallel with SF-02.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Universal Logging Reform | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Unified CLI Runner | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Logging Rollout | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | No error is lost | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Now**: SF-04 committed — no caught error is lost, levels are settings, every logger reaches its handlers, the flag contract holds; FR-5 deleted.
**Next**: none — signed off 2026-10-17.
