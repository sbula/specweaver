# Design: Unprefixed Raw-sqlite3 Tables Outside SQLAlchemy Model Coverage

- **Feature ID**: TECH-023
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Code-verified audit of the TECH registry, 2026-07-31
  (`docs/analysis/tech_registry_audit_2026-07-31.md`, Part 3)

## Problem Statement

`TECH-005` (🟢 Completed, finished and immutable) claims to "refactor all existing database
tables to use a strict domain-prefix naming convention." A code audit found this is not true of
every table: the SQLAlchemy-backed tables (`workspace_*`, `flow_artifact_events`, `llm_*`) are
correctly prefixed, but five tables created directly via raw `sqlite3`/hand-rolled `CREATE TABLE`
statements are not:

- `nodes`, `edges` — `src/specweaver/graph/core/store/repository.py:33,47`
- `pipeline_runs`, `audit_log` — `src/specweaver/core/flow/engine/store.py:33,46`
- `sw_reservations` — `src/specweaver/core/flow/engine/reservation.py:35`

A sixth unprefixed table, `state_schema_version` (`src/specweaver/core/flow/engine/store.py:55`),
was found in the same files during this audit and is in scope for the same reason — it was not
named in the original TECH-005 claim but has the identical root cause (raw-sqlite3 path never
went through the SQLAlchemy-model rename that `TECH-005` actually delivered).

Per finished-stories-immutable, `TECH-005`'s own entry is not edited — this ticket tracks the
residual gap as new work.

## Candidate Approaches (not yet designed)

- Rename these six tables to their domain-prefixed equivalents (e.g. `graph_nodes`, `graph_edges`,
  `flow_pipeline_runs`, `flow_audit_log`, `flow_sw_reservations`, `flow_state_schema_version`),
  mirroring the SQLAlchemy-side prefix convention `TECH-005` established.
- Needs a migration path for the raw-sqlite3 tables (no Alembic coverage here, unlike the
  SQLAlchemy side) — investigate whether these stores already have their own versioning/migration
  mechanism to hook into.

## Non-Goals (proposed, pending design)

- Not a rewrite of `TECH-005`'s delivered SQLAlchemy-table renames — those are confirmed correct
  and out of scope here.
- Not a migration of these stores off raw `sqlite3` onto SQLAlchemy — that's a separate,
  larger architectural question this ticket does not take a position on.

## Next Step

Run through `specweaver-design` to confirm the target names and produce a migration plan for the
raw-sqlite3 stores.
