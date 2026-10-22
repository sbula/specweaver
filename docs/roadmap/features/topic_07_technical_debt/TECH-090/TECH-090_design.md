# Design: The Database Is Opened Three Ways, and the API Server Skips Migrations

- **Feature ID**: TECH-090
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 8 below.

## Problem Statement

The workspace database is opened three ways with different pragmas and pooling; `sw serve` skips the
bootstrap and migrations the CLI runs; config owns the engine; dead write-queue code remains.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **CW-5** — "Pure-logic" config owns the SQLAlchemy engine, an asyncio write queue and a
  dead-letter log in the working folder. Where: `core/config/context.yaml:11`, `database.py:29-292`.
- **CW-6** — The write queue has no producer; project-name helpers are dead copies of
  `workspace/store.py`. Where: `database.py:103,216,248-261`.
- **CW-7** — Three ways to open the database (FK pragma and pooling differ); two sync-async bridges.
  Where: `database.py:277,285`, `db_bootstrap.py:168`, `async_bridge.run_sync` vs `_core.py:78`.
- **CW-21** — ORM, raw SQL and repository in one file; memory tables register through an import side
  effect; "store" means two things. Where: `workspace/store.py` (491 lines), `memory/store.py:19`,
  `db_bootstrap.py:10`.
- **X-14** — Four private `_now_iso` copies beside `commons/timestamps`. Where: `database.py:251`,
  `workspace/store.py:23`, `lineage_repository.py:12`, `engine/store.py:474`.
- **FL-19** — SQLite migration code copied; two modules called `store` with two styles. Where:
  `engine/store.py:129` vs `reservation.py:29`, `gates.py:111` vs `sandboxed_execution.py:127`.
- **EP-10** — The CLI bootstraps the DB on every call, the API never; logging is set up only in the
  CLI. Where: `db_bootstrap.py:197`, `serve_router.py:69`, `api/app.py:70`, `cli/main.py:41`.
- **Real defect 4** — `sw serve` opens the database without the bootstrap and migrations the CLI
  runs; a fresh machine's API server can start on an old schema. Where: `interfaces/api/app.py:70`,
  `routers/serve_router.py:69`.

## Goal

One way to open the workspace database, used by the CLI and the API.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-090`. Write each fix's test
red
first.
