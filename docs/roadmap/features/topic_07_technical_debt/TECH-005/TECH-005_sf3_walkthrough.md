# Walkthrough: TECH-005 SF-3 — Prefix Raw-SQLite3 Tables (FR-8)

- **Design**: `TECH-005_design.md` (APPROVED)
- **Plan**: `TECH-005_sf3_implementation_plan.md` (APPROVED, Red/Blue reviewed, 2 cycles)
- **Tasks**: `TECH-005_sf3_task.md` (T0–T4, single commit boundary; Red/Blue reviewed)
- **Commit boundary**: 1 of 1
- **Date**: 2026-08-02

---

## What changed and why

SF-1/SF-2 renamed every SQLAlchemy-managed table to a bounded-context prefix, but six tables
created via raw `CREATE TABLE IF NOT EXISTS` — never touched by SQLAlchemy — remained unprefixed:
`nodes`/`edges` (graph store), `pipeline_runs`/`audit_log`/`state_schema_version` (pipeline state
store), `sw_reservations` (reservation system). This contradicted TECH-005's own "all existing
database tables" claim. SF-3 closes that gap.

Because these back real, persistent, user-owned SQLite files (`graph.db`, `pipeline_state.db`,
`reservations.db`), a blind `CREATE TABLE IF NOT EXISTS <new_name>` would have silently orphaned
every existing installation's data. Each of the three owning classes gained a legacy-table
detect-and-rename step (`ALTER TABLE ... RENAME TO ...`), run before the existing schema-creation
logic, tolerant of partial/corrupt states and concurrent-construction races.

| File | Change |
|---|---|
| `graph/core/store/repository.py` | **+`_rename_legacy_tables()`**; `nodes`→`graph_nodes`, `edges`→`graph_edges` throughout DDL/DML |
| `core/flow/engine/store.py` | **+`_rename_legacy_tables()`**; `pipeline_runs`→`flow_pipeline_runs`, `audit_log`→`flow_audit_log`, `state_schema_version`→`flow_state_schema_version` throughout |
| `core/flow/engine/reservation.py` | **+`_rename_legacy_table()`**; `sw_reservations`→`flow_reservations` |
| `scripts/_refactor_diff_safety.py` | **+`_infer_token_rename_map`, `_surviving_candidates`, `_signature_from_text`, `_normalized_group_text`** — extends the `--kind refactor` gate to recognize a consistent, possibly-multi-pair literal-token rename as safe (see below) |
| `tests/unit/graph/core/store/test_repository_schema.py` | +4 tests: migration+data-preservation, both-exist skip, idempotent-across-construction, `OperationalError` swallowed |
| `tests/unit/core/flow/engine/test_engine_store.py` | +5 tests: v2-shape migration, FK integrity, idempotent-across-construction, both-exist skip, `OperationalError` swallowed |
| `tests/unit/core/flow/engine/test_reservation.py` | +4 tests: same pattern |
| `tests/unit/scripts/test_tests_runner.py` | +11 tests for the gate extension (see below) |
| `tests/unit/graph/core/store/test_{repository_load,purge_stale,repository_flush,repository_helpers}.py`, `tests/integration/interfaces/cli/test_cli_graph_integration.py` | Mechanical `nodes`/`edges` → `graph_nodes`/`graph_edges` substitution |
| `docs/dev_guides/special_patterns_and_adaptations.md` | **+Pattern 25** — Consistent-Rename Fixpoint Inference |

### The gate-extension detour (found running the real gate, not hypothetical)

Every mechanical test update above changes a SQL-string table-name literal in place — neither a
pure addition nor a dotted-path relocation, the only two patterns the refactor-safety gate
(built during TECH-001 SF-04) recognized. Running `python scripts/tests.py cb TECH-005 --kind
refactor` for real hard-blocked on all affected test files with "tests were bent to fit." Per this
session's standing instruction on this exact gate ("extend it, don't bypass it"), the gate gained
one more provably-safe pattern: a consistent literal-token rename, resolved via **fixpoint**
(not a single greedy pass) because real files often need **multiple simultaneous renames**
(`nodes`→`graph_nodes` and `edges`→`graph_edges` in the same file) — five rounds of TDD found and
fixed real bugs in this extension itself:
1. A single-global-pair design rejected legitimate multi-rename files as "ambiguous."
2. Duplicate lines (three identical `INSERT INTO nodes (...)` fixtures) produced spurious
   multi-candidate rejection even though every candidate implied the same pair.
3. Structurally similar lines from *different* simultaneous renames (`SELECT COUNT(*) FROM nodes;`
   vs. an unrelated `...FROM graph_edges;`) produced a genuinely spurious cross-candidate,
   resolved only by making candidate filtering fixpoint-driven against already-established pairs.
4. Bare numeric tokens (`5`→`3`) had to be excluded from candidacy entirely — otherwise a value
   change riding alongside a real rename was silently laundered as "the" rename.
5. A trailing `C901`-complexity violation on the resulting function required extracting
   `_surviving_candidates` to module level.

Also found and fixed: `test_migration_v1_to_v2`'s planned rename+docstring-widening (design doc
D-4) itself failed the (correctly strict) gate, since a rewritten docstring is a genuine content
change, not a mechanical one. Reverted to the original name/docstring with only the two necessary
mechanical SQL substitutions; the coverage D-4 wanted is instead provided by the wholly new
`test_migrates_legacy_table_names_from_v2_shape` (a pure addition, always safe).

---

## Test results

Gate run: `python scripts/tests.py cb TECH-005 --kind refactor` — DAL-C (TECH default baseline).

| Tier | Scope | Result |
|---|---|---|
| Unit | module (`core/flow/engine`, `graph/core/store`) | **495 passed** |
| Integration | module (`core/flow/engine`) | **112 passed** |
| **Grand total** | | **607 passed, 0 failed** |

No tier selected zero tests. Refactor-safety gate: clean (no modified test file flagged).

`tests/unit/scripts/test_tests_runner.py` (the gate's own test suite): **90 passed**.

## Quality gates

| Check | Result |
|---|---|
| `tach check` | `[OK] All modules validated!` |
| `python scripts/quality.py cb` | 10/12 ok; `complexipy` and `cycles` fail — both confirmed pre-existing via `git stash` (identical findings on the clean baseline) and already tracked (`TECH-015` complexity/class-health, `TECH-024` the same 4 import cycles); zero findings in either check touch any file this SF changed |
| `python scripts/quality.py doc` | `roadmap_sync` ok, `skill_sync` ok |
| `ruff` / `ruff format` / `mypy` / `suppressions` / `conventions` / `file_sizes` / `class_health` / `test_basenames` / `useless_asserts` | all ok |

## HITL gate decisions

| Gate | What was found | Decision |
|---|---|---|
| Implementation plan (Phase 4/5) | Migration-safety design, D-1–D-5, Red/Blue 2 cycles / 7 findings | **Approved, proceed to dev** |
| Task list (Phase 2.5 of `dev`) | T0–T5 breakdown, Red/Blue 1 cycle / 4 findings (gate-extension necessity, FR-1–7 pre-existing gap forecast) | **Approved, start T0** |
| Pre-commit Phase 2 (test gap) | Coverage matrix, 5 proposed stories (3× untested `OperationalError` branch, 1× missing both-exist test, 1× untested fixpoint-exhausted exit) | **"please, go on"** — approved, implemented all 5 |

No gate was skipped or auto-approved without user response.

## Deferred to T5 (story closure, not yet done)

`check_fr_coverage.py TECH-005` — confirmed FR-8 will pass once this commit lands; FR-1–7
(SF-1/SF-2, delivered before this citation gate existed) will still fail on citation, not on
missing behavior. Per finished-stories-immutable, routes to a new TECH ticket via
`specweaver-ticket` (mandatory user confirmation), not a fix to SF-1/2's own files.

---
# Red/Blue Team Review Report — Phase 7.5 (Code)

## Summary
- **Target**: TECH-005 SF-3 code changes (`repository.py`, `store.py`, `reservation.py`,
  `_refactor_diff_safety.py`), post-implementation, pre-commit
- **Cycles**: 2
- **Findings**: 4 (Cycle 1) + 3 (Cycle 2) = 7
- **Critical/High fixes applied**: 2

## Corrections Made
- **RED-1.1 (HIGH)**: the plan-level review's BLUE-1.1 claimed the `with conn:` block gives
  transactional atomicity across the multi-table rename loop. **Empirically disproven** — Python's
  `sqlite3` module auto-commits DDL statements individually; a `with sqlite3.connect(...) as conn:`
  block does NOT roll back an already-executed `ALTER TABLE` when a later statement in the same
  block raises (verified directly: table remained renamed after a simulated crash). The actual
  safety property is different and better than claimed: each table's rename is independently
  idempotency-checked against `sqlite_master` on every construction, so a crash mid-loop leaves a
  genuinely half-migrated DB that the very NEXT construction transparently finishes — resumability,
  not atomicity. Added a dedicated test per multi-table file
  (`test_sqlite_repository_resumes_a_half_migrated_state`,
  `TestStoreSchema::test_resumes_a_half_migrated_state`) proving this directly, with real data in
  both the already-renamed and still-pending tables.
- **RED-1.2 (HIGH)**: `except sqlite3.OperationalError: pass` (via `contextlib.suppress`) in all
  three rename methods was over-broad — it silently swallowed ANY `OperationalError`, not just the
  intended "another process already renamed it" race. A genuine transient failure (lock contention,
  disk I/O) would be silently absorbed, and construction would proceed straight to
  `CREATE TABLE IF NOT EXISTS`, creating an empty new table and silently orphaning the untouched old
  table's data — precisely the failure mode this entire ticket exists to prevent, just relocated
  into the error-handling path instead of the happy path. Fixed in all three files: the `except`
  now re-checks `sqlite_master` for the new name before swallowing — only re-raises if the new name
  genuinely still doesn't exist. Added a `[Hostile]` test per file proving a non-race
  `OperationalError` (`"disk I/O error"` / `"database is locked"`) propagates rather than being
  swallowed.
- Removed the now-unused `contextlib` import from all three files (the fix replaced
  `contextlib.suppress` with an explicit `try`/`except` that conditionally re-raises).

## Accepted Risks
- **RED-2.1 (the re-check fix's own residual TOCTOU)**: the re-check itself is not a lock — a
  third process could theoretically race between the re-check query and this function returning.
  Accepted: this is the same class of already-accepted risk as the plan review's "not fully
  atomic" (RED-1.1 there), and narrows the false-swallow window from "unconditional" to "one
  query's duration" — a substantial improvement over the prior state, not a claim of perfect
  mutual exclusion.
- **RED-2.2 (pre-existing, out of scope)**: `store.py`'s v1→v2 migration
  (`ALTER TABLE ... ADD COLUMN parent_run_id` followed by a separate version-bump `INSERT`) has the
  same DDL-non-atomicity exposure RED-1.1 found — a crash between the two leaves `version` still
  `1` with the column already added, and the NEXT construction's retry of `ADD COLUMN` would raise
  `duplicate column name`, uncaught. **Confirmed pre-existing** (this logic is unchanged by SF-3,
  only its table names were mechanically substituted) and unrelated to this ticket's own new rename
  logic. Not fixed here; flagged to the user as a candidate for a new TECH ticket rather than
  silently left undocumented.
- **RED-2.3 (LOW)**: `store.py`/`reservation.py`'s connections set no `PRAGMA busy_timeout` (unlike
  `repository.py`'s `5000`ms), making a raw lock-contention `OperationalError` more likely to
  surface there under real concurrency. Accepted: RED-1.2's fix means such an error now propagates
  loudly (a construction-time failure) instead of silently corrupting state either way — tuning
  retry behavior is a separate, non-blocking improvement, not a safety gap.

## Cycle Log

### 🔴 RED-1.1 — see Corrections Made
### 🔵 BLUE-1.1 — VALID, FIX REQUIRED — see Corrections Made
### 🔴 RED-1.2 — see Corrections Made
### 🔵 BLUE-1.2 — VALID, FIX REQUIRED — see Corrections Made
### 🔴 RED-1.3 (MEDIUM) — see Accepted Risks (RED-2.2, escalated from a Cycle 1 sighting)
### 🔵 BLUE-1.3 — VALID, ACCEPTED RISK — pre-existing, not this ticket's regression
### 🔴 RED-1.4 (LOW) — see Accepted Risks (RED-2.3)
### 🔵 BLUE-1.4 — VALID, ACCEPTED RISK — superseded by RED-1.2's fix
### 🔴 RED-2.1 / 🔵 BLUE-2.1 — see Accepted Risks
### 🔴 RED-2.2 / 🔵 BLUE-2.2 — see Accepted Risks
### 🔴 RED-2.3 / 🔵 BLUE-2.3 — see Accepted Risks

**Cycle 2 findings** (0 CRITICAL, 0 HIGH, 1 MEDIUM < 5, 2 LOW < 10) fall below every continuation
threshold — review complete.

*(End of Red/Blue Team Review Report)*
