# task.md — B-SENS-03 SF-06, CB-1: a chunk knows its scope

**Plan**: `docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf06_implementation_plan.md`
**Boundary**: CB-1 of 3 · **FR-14** · **Tier**: unit

- [x] **T1** — Red: `tests/unit/workspace/analyzers/test_chunking_scope.py`
- [x] **T2** — `visibility`, `package`, `unit` on `Chunk`
- [x] **T3** — `chunk_source(..., markers=frozenset())`; `unit` is `""` without them
- [x] **T4** — Mutants: `unit` falls back to `package` · visibility is always `unknown`

**Every check before the commit**: full suite · `quality.py cb` · `doc` · ruff · ruff format ·
mypy · complexity · class health · duplication · conventions · tach.

---

# CB-2 — two layers  (FR-12)

- [x] **T1** — Red: `tests/unit/workspace/analyzers/test_chunking_layers.py`
- [x] **T2** — `layer` on `Chunk`; one skeleton chunk per reported symbol, never merged, never
      split (measured max 1,563 against 4,000 — the pathological case still goes through `_emit`)
- [x] **T3** — The preamble appears in **both** layers `[agreed 2026-08-26]`
- [x] **T4** — `FR-17` binds the **body** layer, **both halves**. Narrow the existing tests with
      the reason inline — a skeleton is a doc and a signature concatenated, not a slice of the file
- [x] **T5** — The parser contract grows a fourth call shape; the minimal stub says so
- [x] **T6** — Mutants: skeletons merge · the layer is never set

**Every check before the commit.**
