# Implementation Plan: Agent Memory Bank [corrections of 2026-10-17]
- **Feature ID**: B-INTL-09
- **Design Document**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_design.md
- **Design Section**: §Corrections (2026-10-17)
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_corrections_plan.md
- **Status**: APPROVED by the user 2026-10-17 · built: CB-1 `c2afe191`, CB-2 `ea951f1a`, CB-3 `050f4f55`, CB-4

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | K-1 citations (each test read first) and K-2's missing tests: `recycle_zombies` with no timeout uses 15 minutes; an oversized note through `update_handover_context` is refused or cut; caplog for the propagation (INFO), heartbeat (DEBUG) and collision (WARNING) lines | FR-1, NFR-1, NFR-3, NFR-4, NFR-6, NFR-7, NFR-8 | each new test is mutated (the default, the limit, each log line) and must go red |
| CB-2 | K-3: `HandoverContext` refuses unknown fields; the hydrator reports such a note as unreadable | NFR-5 | a note with an unknown field is accepted today |
| CB-3 | K-4: `EXPLAIN QUERY PLAN` for the zombie scan, task claiming and the dependency walk fails on `SCAN` of a table; the missing index, added at start-up as `CREATE INDEX IF NOT EXISTS` so older databases gain it | NFR-9 | the zombie scan's plan, measured first |
| CB-4 | K-5: the mutant corpus, run, every survivor answered with a test | FR-1..FR-9 | — |

## Research Notes

- Tests that prove today (read 2026-10-17): FR-1 `test_memory_store.py` (four models, the reason enum, cascades);
  NFR-1 `test_int_9_occ_concurrent_race`, `test_acquire_task_version_mismatch`; NFR-4 `test_e2e_9_zombie_reaping_boundary_jitter` (14 / 16 minutes);
  NFR-6 `test_handover_context_truncation`, `test_handover_context_size_limit_exceeded`, `test_handover_context_length_limit`;
  NFR-7 `test_database.py::TestLiveSessionsEnforceForeignKeys` (cited wrongly as FR-6).
- The OCC collision warning: `repository/core.py:481`. The breaker: `resilience.py:84` (`>= 3`).
- Indexes: `idx_task_status_project` (status, project_name), `idx_task_heartbeat` (status, last_heartbeat_at); the zombie scan
  filters project, status and heartbeat with an `OR IS NULL`.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| — | none open: Q1–Q5 settled in the design `[agreed 2026-10-17]` | — |
