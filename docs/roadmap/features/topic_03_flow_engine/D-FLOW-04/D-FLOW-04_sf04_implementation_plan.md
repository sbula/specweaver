# Implementation Plan: Unified Runner Architecture [SF-04: No error is lost]
- **Feature ID**: D-FLOW-04
- **Sub-Feature**: SF-04 — No error is lost
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/D-FLOW-04/D-FLOW-04_design.md
- **Design Section**: §Sub-features → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/D-FLOW-04/D-FLOW-04_sf04_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-17 · built: CB-1 `d2816fc3` … CB-9

**FRs owned**: FR-4, FR-6, FR-7, FR-8, FR-9, NFR-2, NFR-3; closes FR-1..FR-3 citations · **Depends on**: SF-01 (committed)

## Goal

No caught error leaves `src/specweaver/` without a trace or a stated reason, and the commit gate keeps
it so; what the console and the log file show is each project's setting.

## Shape

| Piece | Where | Tag |
|---|---|---|
| the check: every `except` logs (a call on a name holding `log`), raises, names its caught error in its body, or has `# expected: <why>` on its `except` line; prints each offender as `path:line` and the count of `# expected:` reasons | `scripts/check_lost_errors.py` | NEW |
| ruff `G` (logging format) in the rule set; the 18 f-string log calls rewritten to `%s` | `pyproject.toml`, `src/` | MODIFY |
| each of the 116 handlers the check names (of the 209 that neither log nor raise, 93 use their error and already pass): a log line (FR-8: DEBUG, or WARNING when the lost error changes what the user gets) or a one-line reason | `src/specweaver/**` | MODIFY |
| the check joins the `cb`, `sf` and `feature` gates | `scripts/_quality_checks.py`, `scripts/quality.py` | MODIFY |
| `console_log_level` per project (default `WARNING`), added like the other columns; `sw config set-log-level --console`; `get-log-level` shows both; `setup_logging(console_level=...)`, also on a repeated call | `workspace/store.py`, `core/config/bootstrap/db_bootstrap.py`, `core/config/interfaces/cli.py`, `telemetry_logger.py`, `interfaces/cli/main.py` | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the check, in the `feature` gate only, and ruff `G` with its 19 fixes (18 `G004`, 1 `G003`) | FR-6 (the check), NFR-3 | the check on fixture files: a silent `pass`, a `return None`, an unused `as e` — red until it exists; `ruff --select G004` finds 18 |
| CB-2 | `core/` and `commons/` handlers (38) | FR-6, FR-8 | the check names each of them |
| CB-3 | `sandbox/` handlers (41) | FR-6, FR-8 | the check names each of them |
| CB-4 | the rest (37): `infrastructure`, `interfaces`, `assurance`, `graph`, `workflows`, `workspace` | FR-6, FR-8 | the check names each of them |
| CB-5 | the check joins the gates, at zero | FR-6 | a planted silent `except` fails `quality.py cb` |
| CB-6 | the console level as a setting | FR-7, NFR-2 | `set-log-level --console` is refused today; an INFO line never reaches the console |
| CB-7 | every logger reaches its handlers: ruff `T20`; a check that `getLogger` takes `__name__` (or a name under it) and no root-logger call (`logging.error(...)`) remains; the dead-letter logger renamed under its module, still writing its own file only | FR-9 | the check names `database.py`'s `dlx_worker_<id>` and its two `logging.critical` calls |
| CB-8 | the flag contract: a recorded list of every command's flags, and a test that fails on any removed, renamed or unrecorded flag | FR-4 | the test fails until the list exists |
| CB-9 | the closure: FR-1..FR-3 cited by the tests that prove them (read first), FR-5 deleted | FR-1, FR-2, FR-3 | `check_fr_coverage.py D-FLOW-04` fails today |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | the check on fixture sources, one per accepted and refused shape, including `except*`, nested handlers, a reason on the wrong line |
| CB-2..4 | unit / integration where behaviour changes | each handler turned WARNING because the user got a wrong result gets a test of that result — e.g. the Rust runner's error now carries its message |
| CB-5 | integration | `quality.py cb --only lost_errors` on a temporary tree with one planted offender fails, on a clean one passes |
| CB-6 | integration + e2e | a real database gains the column, keeps old projects at WARNING; `sw config set-log-level --console INFO` then a command's INFO line is on stderr, and back at WARNING it is not |

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `raise-not-seen` | the check accepts no `raise` | CB-1 |
| `reason-anywhere` | the reason is accepted on any line | CB-1 |
| `unused-name-counts` | an `as e` never used counts as use | CB-1 |
| `gate-without-check` | the check is left out of `cb` | CB-5 |
| `console-level-ignored` | `setup_logging` keeps WARNING on the console | CB-6 |
| `old-projects-not-warning` | the column's default | CB-6 |
| `rust-error-dropped` | the Rust runner's error message | CB-3 |

## Research Notes

- Measured 2026-10-17 with an AST scan: 425 handlers; 127 log, 89 raise; 209 do neither — 93 use the
  error, 56 drop it (`pass`, `continue`, a constant return), 60 do something else. By package: `core/flow`
  53, `sandbox/filesystem` 24, `sandbox/language` 17, `infrastructure/llm` 18, `interfaces/cli` 16.
- `ruff --select G004`: 18; `S110`/`S112`: 7 (all inside the 56); `BLE001`: 140.
- Gates are declared in `scripts/quality.py:103-137` and built in `scripts/_quality_checks.py`
  (`make(name, roots, runner, script=...)`); `suppressions` is the model to copy.
- File level: `workspace/store.py:50` `log_level`, `get_log_level` / `set_log_level` (`:254-271`), read
  in `interfaces/cli/main.py:44-53` and passed to `setup_logging(project_name, level)`
  (`telemetry_logger.py:102`). The console handler is fixed at WARNING (`:165`); a repeated call for
  the same project updates only the file handler (`:132-139`).
- Columns are added idempotently in `core/config/bootstrap/db_bootstrap.py` (`_add_call_status` is
  the pattern), never Alembic.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| — | none open: the design settled every trigger `[agreed 2026-10-17]` | — |
| Q1–Q4 (closure) | FR-1 reworded; FR-4 gets the flag contract; FR-5 deleted; FR-9 every logger reaches its handlers | `[agreed 2026-10-17]` |

## Backlog

none
