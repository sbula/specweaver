# task.md — B-SENS-03 SF-06, CB-1: a chunk knows its scope

**Plan**: `docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf06_implementation_plan.md`
**Boundary**: CB-1 of 3 · **FR-14** · **Tier**: unit

- [x] **T1** — Red: `tests/unit/workspace/analyzers/test_chunking_scope.py`
- [x] **T2** — `visibility`, `package`, `unit` on `Chunk`
- [x] **T3** — `chunk_source(..., markers=frozenset())`; `unit` is `""` without them
- [x] **T4** — Mutants: `unit` falls back to `package` · visibility is always `unknown`

**Every check before the commit**: full suite · `quality.py cb` · `doc` · ruff · ruff format ·
mypy · complexity · class health · duplication · conventions · tach.
