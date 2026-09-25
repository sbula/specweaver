# INT-US-04 SF-01 — Core Flow DB Integration

**Status**: APPROVED 2026-08-14. Delivered 2026-08-14..15 in four commit boundaries. · **FRs owned**:
FR-1, FR-2, FR-3 · **Depends on**: none · Design: [INT-US-04_design.md](INT-US-04_design.md)
§Sub-features → SF-01

## Goal

Run-scoped persistence of validation output, and close the resume gap that loses it. Decided by the
user on 2026-08-14 after `TECH-017` surfaced `INT-US-04` C1 as the audit's single open decision:
persistence **was** intended. All three FRs were amended or clarified in the design that day:

| FR | Says |
|---|---|
| FR-1 | Extract validation findings into `StepResult.output` **without loss** — including each `Finding`'s line, severity and suggestion |
| FR-2 | Persist rule results against `run_id` in a **queryable table in the pipeline state DB** (`flow_validation_results`) |
| FR-3 | Restore `context.feedback` **on resume**, so a resumed run regenerates against the same findings a same-session run would have seen |

**Out of scope:** the contract's *"sanitized"* clause (maps to `E-VAL-03`, unbuilt — `INT-US-04` C2's
sanitization half stays `unproven` however this lands); cross-run history or any query/CLI surface
over it.

Preconditions verified green before dev: `check_story_preconditions.py INT-US-04`, exit 0, 6 passed.

Two deliverables: **replay fixes the defect, the table closes the claim** (D-1).

## Where it plugs in

Line refs are as of 2026-08-14.

- **R-1.** `assurance/validation/context.yaml` declared `exposes: [ValidationRunner,
  ValidationResult, RuleSeverity]` — all three with zero occurrences in `src/`. The real surface:
  `run_rules()` / `count_by_status()` / `all_passed()` over `RuleResult`, `Finding`, `Severity`,
  `Status`. (`assurance/validation/models.py`)
- **R-2.** `StateStore.save_run` serializes `[r.model_dump() for r in run.step_records]` into
  `flow_pipeline_runs.step_records` as one JSON blob; `StepResult.output` rides along. No
  `rule_id`/`status`/`severity` column anywhere. (`store.py:175`)
- **R-3.** The handler builds `output` as `{"results": [{"rule_id", "status", "message"} …],
  "total", "passed"}` — `Finding` dropped at the handler boundary.
  (`handlers/validation.py:108-114`)
- **R-4.** `gates.inject_feedback` writes `context.feedback[to_step] = {"from_step": …, "findings":
  result.output}`, called on the `loop_back` verdict; `generation.py:85-87` and `draft.py:36-37`
  **pop** it into the next prompt. In memory, one process. (`gates.py:146`, `step_execution.py:305`)
- **R-5.** `feedback` is a plain `RunContext` field. Neither `store.py` nor `hydration.py`
  references it; `resume()` → `rehydrate_from_records` rebuilds `plan_context` and **nothing else**.
  (`run_context.py:157`)
- **R-6.** Same bug class, fixed twice on this path: **`TECH-021`** retains the failing step's
  `run.step_records[step_idx].status/result` on loop-back (it was `status=RUNNING`, `result=None`,
  so a human resuming *"had no record of why the later step failed"*); **`TECH-033`** persists
  `attempt` into the step record (`gates.py:229`) (*"a resume restarted it at zero"*). The loop
  **target's** record is reset to `PENDING` / `result=None`. (`gates.py:222-223`, `:229`,
  `:232-233`)
- **R-7.** `hydrate_plan_context` is *"the single hydration point: the runner calls it after a step
  advances, and `resume()` replays it over persisted step records, so the live path and the
  cross-session path cannot drift apart."* Never raises; a malformed artifact degrades to a WARNING.
  `default=str` is **not optional** — without it an output carrying a `Path`/`set` raises on the
  LIVE path but hydrates fine on RESUME. *"Sharing this function is only half the guarantee; the
  serialization semantics must match too."* (`hydration.py:88`, `:110-115`)
- Join points: advance (both gate and no-gate paths) and resume. (`step_execution.py:474`,
  `runner.py:216`)
- **R-8.** `_ensure_schema` runs `conn.executescript(_STATE_SCHEMA_V2)` on **every** construction;
  every statement is `CREATE TABLE IF NOT EXISTS`, so a new table appears on existing DBs with no
  migration. The `flow_state_schema_version` row and the v1→v2 `ALTER TABLE` path are for **column**
  additions. (`store.py`)
- **R-9.** `StateStore` is raw `sqlite3` in WAL mode (stdlib), not SQLAlchemy — no session, nothing
  to await. `pyproject.toml` needs no change. (`store.py`)
- **R-10.** `core.flow`'s `depends_on` already lists `specweaver.assurance.validation`, and that
  core imports nothing from `core.flow` (only its `interfaces/` submodule does, lazily — a separate
  tach module). Importing `RuleResult` is legal, but not done: the handler already flattens to
  primitive dicts, so the store persists primitives and imports nothing. (`tach.toml:46`)
- `store.py` imports only `commons.json` and `engine.state`; the state DB is declared *"isolated
  from the configuration database"*. (`store.py:7`)

R-1 explains the contract's wording and `TECH-017`'s finding that *"`ValidationResult` does not appear
in `src/`"*: the design was written against a **declared** interface. **Every reference here is to
`RuleResult` / `Finding`.** Across the tree 7 modules have stale `exposes`; `assurance/validation` is
the only one at **3 of 3**. Nothing enforces the field — `tach.toml` does not read it, and no script
does (but see RB-1).

R-6 matters: `TECH-021` already persists exactly the payload `inject_feedback` injects — the failing
step's `result.output`. The data FR-3 needs is *already in the store*; the replay was missing.

Test precedents (R-11):

- `tests/unit/core/flow/engine/test_runner_rehydration.py` — the `INT-US-21` FR-3 proof, with the
  boundary cases inherited here (empty records, more records than steps, reordered pipeline).
- `tests/unit/core/flow/engine/test_engine_store.py` — schema/migration test shape.
- `tests/integration/core/flow/engine/test_pipeline_state_persistence.py` and
  `test_rehydration_integration.py` — the integration tier for this seam.
- `tests/unit/core/flow/engine/test_retry_budget_across_resume.py` — `TECH-033`'s across-resume
  proof, the closest analogue to FR-3's test.

Architecture check: all changes in `core/flow/engine/` and `core/flow/handlers/`, inside the `flow`
module (archetype `orchestrator`; `pipeline_state.db` is its private store). No new module, no new
`context.yaml`, no circular imports, dependency direction unchanged (R-10); `tach check` stays green.
Config/state separation honoured — the reason FR-2 moved off the Config DB. No `_schema.py`/mixin
split: the state DB owns its schema inline in `store.py`.

## Changes

Four commit boundaries, each independently committable, each naming its tier per `ADR-003`.

### CB-1 — FR-1: stop dropping `Finding` (unit)

Widen the `results` payload in `handlers/validation.py` at :108 (`validate+spec`) and :245
(`validate+code`) to carry each rule's full `Finding` list — `message`, `line`, `severity`,
`suggestion` per finding (D-3). Built as `_rule_payload()`, used by both call sites, plus a second
shared helper `_validation_output()` (see As built).

**Done when:** (1) dropping the `findings` key from the payload builder turns the test red — a test
that still passes asserts on `total`/`passed`, not on FR-1; (2) the measured `step_records` blob-size
delta on a real run is recorded here (RB-6) — an unrecorded measurement blocks the boundary.

### CB-2 — FR-2: the table, its writer, its reader (unit + integration)

- `flow_validation_results` in `_STATE_SCHEMA_V2`, index on `run_id` (RB-7), version row 3 (D-8).
- **Grain: one row per FINDING** (D-11): `(run_id, step_name, attempt, rule_id, finding_index)` with
  `message`, `line`, `severity`, `suggestion` as real columns, append-only with an autoincrement
  `id`. A rule with no findings still gets one row, `finding_index` and the four finding columns
  `NULL` — otherwise *"did S01 run, and did it pass?"* is unanswerable.
- `save_validation_results()` and `StateStore.get_validation_results(run_id, *, step=None)` returning
  `list[dict[str, object]]` (RB-9).
- **Write point: `step_execution.py:465`, straight after `execute_step()`, before `resolve_outcome`**
  (D-10) — catches every result once per attempt whatever the verdict. The run row already exists
  there (`runner.py:258`), so the foreign key holds. Built as `persist_validation_results`.
- Rows carry the **validating step's own** `attempt` (RB-5). Rule results only — not `run_tests` (D-5).

Replaced: the advance join point (`:474`, beside plan hydration). It is reached only when
`resolve_outcome` returns `PROCEED`; a failing validate step returns `CONTINUE` (loop-back) or
`RETURN` (no gate, or HITL park), so every failing result — the ones FR-3 replays — would have been
dropped. Hydration belongs on advance (a failed step has no plan); persistence does not.

Per `ADR-003` this SF owns the integration test; no later story will write it. **Done when** the
writer neutralised to a no-op turns the integration test red.

### CB-3 — FR-3: restore feedback on resume (integration)

`replay_feedback(pipeline, run, context)` in `hydration.py`, called from `rehydrate_from_records`,
reusing `GateEvaluator.inject_feedback` and carrying `default=str` semantics (R-7). The replay
condition is a **conjunction** (RB-4):

1. the gate's `loop_target` names the step at `run.current_step`;
2. that target's record has `result=None` (the discriminator: `result is None`) and status `PENDING` or `RUNNING` (`gates.py:232-233`
   resets it to `PENDING`; `mark_step_running` then persists `RUNNING` — two reachable crash points,
   W-1);
3. the **source** step's record carries a `result` whose status is not `PASSED` — checkable only
   because of `TECH-021` (R-6).

Where two gates share a target, the **highest-indexed** eligible source wins (RB-2). Feedback is
written under the **target** step's name (RB-3), because that is what `generation.py:87` pops.

Write the test after CB-2's interface exists and before the restore behaviour does, and **record the
red and its reason** — the one piece of evidence a `Proves:` tag can never supply. **Done when**
deleting the `replay_feedback` call from `rehydrate_from_records` turns the test red: the whole defect
is an absent call.

### CB-4 — D-4/RB-1: correct `assurance/validation`'s declared interface (unit)

`exposes` is set **equal to `tach.toml`'s** module-qualified expose list (17 names: `executor`,
`pipeline_loader.load_pipeline_yaml`, `models.RuleResult`, …), so a `tach_sync` is a no-op (D-12).
**Done when** `tach check` is green after the edit, and a unit test asserts every name resolves to a
real symbol, the two lists match, and the field is non-empty (`tach_sync` skips the interface block
when `exposes` is falsy — emptying it would *delete* the enforced interface rather than fail).

### Files

| File | Tag | Change |
|---|---|---|
| `src/specweaver/core/flow/handlers/validation.py` | `[MODIFY]` | Full `Finding` list in the `results` payload at **:108** (`validate+spec`) and **:245** (`validate+code`) (D-3) |
| `src/specweaver/core/flow/engine/store.py` | `[MODIFY]` | `flow_validation_results` in `_STATE_SCHEMA_V2` + `run_id` index; `save_validation_results()`, `get_validation_results()`; version 3 (D-8) |
| `src/specweaver/core/flow/engine/hydration.py` | `[MODIFY]` | `replay_feedback(pipeline, run, context)`, called from `rehydrate_from_records` (D-1) |
| `src/specweaver/core/flow/engine/step_execution.py` | `[MODIFY]` | Call the validation-results writer at **:465**, before `resolve_outcome` (D-10) |
| `src/specweaver/assurance/validation/context.yaml` | `[MODIFY]` | `exposes` → equal to `tach.toml` (D-4 / RB-1 / D-12) |
| `tests/unit/core/flow/handlers/test_validate_spec_findings.py` | `[NEW]` | FR-1 |
| `tests/unit/core/flow/engine/test_validation_results_store.py` | `[NEW]` | FR-2, store methods + schema |
| `tests/integration/core/flow/engine/test_validation_results_persistence.py` | `[NEW]` | FR-2 seam |
| `tests/integration/core/flow/engine/test_feedback_replay_across_resume.py` | `[NEW]` | FR-3 |
| `docs/dev_guides/pipeline_engine_guide.md` | `[MODIFY]` | Record the table's grain (D-9) |

No new module, no new `context.yaml`, no `pyproject.toml` change (R-9).

## Tests

| # | Check | Tier |
|---|---|---|
| 1 | `Finding` fields survive into `StepResult.output` for `validate+spec` and `validate+code` | unit |
| 2 | Blob-size delta measured on a real run and recorded in this plan | measurement |
| 3 | Schema creates on a fresh DB **and** on an existing v2 DB without migration (R-8) | unit |
| 4 | `save_validation_results` / `get_validation_results` round-trip, including `attempt` | unit |
| 5 | A real pipeline run writes rows a real query reads back | integration |
| 6 | Resumed run restores feedback under the target step's name, and the consuming handler sees it | integration |
| 7 | Replay does **not** fire when no loop-back occurred (RB-4) | integration |
| 8 | Replay picks the highest-indexed eligible source when two gates share a target (RB-2) | integration |
| 9 | Already-consumed feedback is not re-injected (D-6) | integration |
| 10 | A failing write logs WARNING and does not raise (D-7) | unit |
| 11 | Every name in `assurance/validation`'s `exposes` resolves to a real symbol (RB-1) | unit |
| 12 | `tach check` green; full suite green | gate |

NFR-1: `StateStore` is sync `sqlite3` in WAL mode and the writes are `INSERT`-only. NFR-2: verified
in §Where it plugs in and re-checked by CB-4's `tach check`. NFR-3: `test_mcp_flow_e2e.py` and every existing pipeline YAML keep working without modification; R-8
is why no data migration threatens that.

## Decisions (audit)

Taken at the gate 2026-08-14 (D-1..D-4), by proposal (D-5..D-9), and during dev (D-10..D-12).

- **D-1** — **Replay restores; the table gets a reader.** FR-3 replays feedback from persisted step
  records, mirroring `hydrate_plan_context` (R-7). The table serves FR-2 and ships with
  `get_validation_results`, exercised at integration tier. *Why:* Without a reader the table has no
  in-code consumer, and a write-only table is what a later tidy-up deletes; any future history
  feature builds on it. Rejected: the table as the restore path — two persistence mechanisms for one
  payload, the drift `hydration.py:110-115` warns about.
- **D-2** — **Append-only**, autoincrement `id` plus `(run_id, step_name, attempt, rule_id)` —
  matches `flow_audit_log`'s shape. `attempt` is a real column, not inferred from insertion order.
  *Why:* Overwrite-per-rule would lose a retried run's earlier failures — what `TECH-021` was filed
  to stop losing. Grain refined by D-11.
- **D-3** — **FR-1 carries the full `Finding` list**; the cost is measured, and a cap is proposed
  only if the measurement shows a problem. *Why:* A silent cap is truncation that reads as
  completeness; if one is ever needed, FR-1's wording changes with it.
- **D-4** — **Fix the stale `context.yaml` (R-1) in this SF.** *Why:* Three wrong lines directly
  produced the design's wrong FR-1; `AD-2` and the no-inflation rule point at fixing in place.
  Target list corrected by D-12. The other six stale modules are reported and left — sweeping them,
  and adding a check against regrowth, is a separate concern.
- **D-5** — **Rule results only.** `validate+spec` (`validation.py:108`) and `validate+code` (:245)
  persist; `run_tests` does not. *Why:* Its payload has no `rule_id`; forcing it in makes the table
  mean two things.
- **D-6** — **Replay keys on the loop target still pending** (`gates.py:232-233`). *Why:*
  Distinguishes *feedback pending* from *already consumed*; otherwise a resumed run could re-apply a
  stale round — the bug `generation.py:80-84` guards against in-session by popping. Refined by RB-4
  and W-1.
- **D-7** — **Persistence never raises.** Logs WARNING with the run id; that path has its own test.
  *Why:* Matches `hydrate_plan_context` and `flush_telemetry`; an untested degradation path is how
  `TECH-032`'s vacuous successes happened.
- **D-8** — **Schema version bumps to 3.** *Why:* Not needed for correctness (R-8); the recorded
  version reflects reality.
- **D-9** — **`docs/dev_guides/pipeline_engine_guide.md` records the table's grain.** *Why:* The
  next reader looks there for engine persistence.
- **D-10** — **Write point at `step_execution.py:465`**, before `resolve_outcome`. *Why:* See CB-2.
  Found by the CB-2 task-list Red/Blue, before implementation.
- **D-11** — **One row per FINDING.** Denormalized, not two tables. *Why:* Per-rule grain left
  findings only a JSON column — the opaque blob CB-1 had rescued them from. A join for a feature
  whose only consumer is a test is work without a reader (`KISS`); the redundancy is bounded by the
  ~170 bytes/finding measured.
- **D-12** — **`exposes` = equality with `tach.toml`.** *Why:* D-4 named `run_rules`,
  `count_by_status`, `all_passed`, `RuleResult`, `Finding`, `Severity`, `Status`. `tach_sync` copies
  the field verbatim into `tach.toml`'s `expose` array and tach **enforces** it; syncing those seven
  would have replaced the 17 correct names and broken every import of `executor`, `loader` and
  `pipeline_loader` — RB-1's failure from the other direction.
- **Q-11** — Base contract `⬜ Pending` → `✅` on delivery — a status decision for the user, no code
  depends on it. *Why:* Resolved at close: flipped in `33561183` (see design).

**Red/Blue** — three cycles, 11 findings, one CRITICAL; cycle 3 produced nothing above LOW (the
stopping condition).

- **RB-1** (CRITICAL) — `tach.toml` carries 20 `[[interfaces]]` blocks, and
  `tach_sync.sync_tach_toml` (`workspace/project/tach_sync.py:53-63`) **generates them from
  `exposes`**. `tach.toml` held the real surface (`models`, `models.RuleResult`, `models.Status`,
  `executor`, `loader`, …; no `ValidationResult`). A tach sync would have replaced a correct 12-name
  expose list with three fictional names and broken every import from `assurance.validation`.
  **Blue:** D-4 promoted; CB-4 done-when adds `tach check` after the edit and a resolve-every-name
  test.
- **RB-2** (HIGH) — `inject_feedback` keys by **`to_step`**; two gates can share a `loop_target`
  (`run_tests` → `generate_code` and `validate_code` → `generate_code`, the shape `sw implement`
  has). **Blue:** Replay the **highest-indexed** eligible source — the "later index wins" rule of
  `rehydrate_from_records` (`test_runner_rehydration.py::test_later_index_wins`). Own test.
- **RB-3** (HIGH) — `generation.py:87` pops `context.feedback[step.name]` for the step **about to
  run**. Keying on the failing step's name persists a dict nothing reads, and every "restored"
  assertion still passes. **Blue:** Write under the target's name; the test asserts the *consuming*
  handler sees it.
- **RB-4** (HIGH) — Every step record starts `PENDING`, so "target is `PENDING`" alone fires on runs
  that never looped back. **Blue:** The conjunction in CB-3.
- **RB-5** (MEDIUM) — Two step records are in play — which `attempt`? **Blue:** The validating
  step's own.
- **RB-6** (MEDIUM) — D-3's measurement had no failing condition. **Blue:** Moved into CB-1's
  done-when.
- **RB-7** (MEDIUM) — `flow_artifact_events` indexes `artifact_id`; every query here is by `run_id`.
  **Blue:** Index `run_id`.
- **RB-8** (MEDIUM) — `validate_code` is report-only behind a `CONTINUE` gate
  (`workflows/implementation/interfaces/cli.py`), never loops back, so its findings never reach
  `inject_feedback`. **Blue:** Its rows serve **FR-2 only** — stated so nobody "fixes" their absence
  from regeneration prompts.
- **RB-9** (LOW) — Return type. **Blue:** `list[dict[str, object]]`, matching `get_audit_log`.
- **RB-10** (LOW) — `fan_out.py` gives sub-runs isolated `RunContext`s. **Blue:** Replay covers the
  resumed run only; sub-run feedback is **out of scope**.
- **RB-11** (LOW) — `runner._persist(run)` (`step_execution.py:399`) precedes the results write, so
  a crash between them leaves a run row with no result rows. **Blue:** Acceptable under D-7 (never
  raise, append-only).

**Risks**

| # | Risk | Mitigation |
|---|---|---|
| R-1 | The table ships write-only and is deleted by a later tidy-up | Q-2 (D-1): ship a reader and prove it at integration tier |
| R-2 | Replay re-applies consumed feedback | Q-6 (D-6): key on the target record being pending; test the already-consumed case |
| R-3 | Widened `output` (CB-1) inflates every persisted run record | Q-3 (D-3): measure the blob delta on a real run before capping |
| R-4 | Live and resumed paths drift, the failure `hydration.py` warns about | One replay function for both paths, mirroring `hydrate_plan_context`; `default=str` on both sides |
| R-5 | Scope creep into cross-run history | Named out of scope; Q-2's reader is `run_id`-scoped by signature |

Traps for a fresh agent: the table is **not** the restore path (D-1); the feedback key is the target's
name (RB-3); `PENDING` alone is not a loop-back signal (RB-4); `ValidationResult` does not exist
(R-1). Forward fit: cross-run history builds on CB-2's append-only grain and `get_validation_results`;
`E-VAL-03` (sanitization) would wrap the payload CB-1 widens; `INT-US-04` SF-09's declarative routing
consumes `RunContext`, untouched here. Replay reuses `inject_feedback` (DRY), as
`rehydrate_from_records` reuses `hydrate_plan_context`; `StateStore` stays the adapter and no domain
type crosses into it.

## As built

### CB-1 (2026-08-14)

`_rule_payload()` carries all four `Finding` fields; both call sites use it. 8 unit tests, plus U-1
(multi-rule order and count) and U-2 (sibling tallies survive the widening), both probed to a killed
mutant. A second helper, `_validation_output()`, removed an 11-line clone (the same `output` dict and
`StepResult` shape in both handlers) that `TECH-037`'s duplication gate exposed once the first
extraction re-keyed the remainder; duplication baseline re-frozen 123 → 121.

**Measurement (D-3 / RB-6), 2026-08-14.** `len(json.dumps([rec.model_dump()], default=str))` for one
`validate_spec` step record — the expression `StateStore.save_run` uses (`store.py:175`) — same spec,
with and without the `findings` key. Script: `.tmp/measure_blob.py` (gitignored; the numbers are the
record).

| Spec | Rules | Findings | Before | After | Delta |
|---|---|---|---|---|---|
| `tests/fixtures/good_spec.md` | 12 | 3 | 1 445 B | 2 262 B | **+817 B (+56.5%)** |
| `specs/TestComponent_spec.md` | 12 | 5 | 1 456 B | 2 509 B | **+1 053 B (+72.3%)** |
| deliberately weasel-worded spec | 12 | 10 | 1 382 B | 3 110 B | **+1 728 B (+125.0%)** |

Linear at roughly **170 bytes per finding**, plus about 15 bytes per rule for the empty-list key.
**No cap.** Worst case measured is a **3.1 KB** step record; a pathological 100-finding spec would
reach ~19 KB — far inside anything SQLite or the loop-back prompt cares about. FR-1's *without loss*
stands.

| Mutant | Result |
|---|---|
| drop the `findings` key | `KILLED` ×8 |
| drop `suggestion` (partial loss) | `KILLED` ×3 |
| reverse rule order | `KILLED` ×2 |
| `passed` counts only `PASS` (excludes WARN/SKIP) | `KILLED` ×1 — **single point of protection** |
| `f.severity.value` → `f.severity` | `SURVIVED` — **equivalent**, `Severity` is a `StrEnum` |

The equivalent mutant exposed a vacuous assertion (`"Severity." not in blob` cannot fail for a
`StrEnum`), replaced with `issubclass(Severity, str)`; the source docstring claiming `.value` was
load-bearing was corrected.

| Gate | Result |
|---|---|
| `tests.py cb INT-US-04 --all` | unit 6 107 · integration 58 · e2e 15 — **6 180 passed**, 11 skipped, DAL-D (most critical of `D-FLOW-01`, `E-FLOW-01`, `E-VAL-01`) |
| `quality.py cb` | 13/13 — ruff, `ruff format --check`, mypy, complexipy, tach, file sizes, suppressions, class health, cycles, duplication, coupling, conventions, test guards |
| `quality.py doc` | 9/9 |
| `useless_asserts`, `test_basenames` | green (pulled forward to Phase 2 per §2.5b) |

`--all` is needed: `tests.py cb INT-US-04` selects **integration and e2e only**, because `INT-US-04`
is an integration story, so CB-1's unit-tier change would have passed unverified. With `--all` it
failed at once on a stale FR sweep baseline (242; the new `Proves:` tag cited a previously uncited
FR), re-frozen to 241. The tier rule's own signal — an INT story wanting a unit test means the
capability underneath shipped incomplete — was right here (R-3); the gate still would not run the test.

### CB-2 (2026-08-14)

`flow_validation_results` (one row per finding, index on `run_id`, schema v3),
`save_validation_results` / `get_validation_results`, and `persist_validation_results` in the step
loop. 18 unit + 4 integration tests, including three pre-commit additions for branches the seam
cannot reach: the D-7 never-raises path, a malformed `results` payload, the `attempt` fallback
(`assert mock.called` tightened to `assert_called_once` after `useless_asserts` rejected it).

Mutants: writer as a no-op `KILLED`; **call moved back to the originally planned `:474` `KILLED`**
(proof D-10 was necessary); `except Exception` narrowed `KILLED ×1` (single point of protection).
Touched: three `version == 2` pins in `test_engine_store.py` (now 3); FR-sweep baseline 241 → 240.

### CB-3 (2026-08-15)

`replay_feedback` in `hydration.py`, called from `rehydrate_from_records`, reusing
`GateEvaluator.inject_feedback`. 11 unit + 4 integration tests. Done-when mutant (delete the call)
`KILLED`.

The recorded red: *"the regenerating step was handed NO feedback on resume"*. The integration test
constructs the interrupted state directly — in one process a loop-back is followed at once by
re-execution, so the paused-at-target state exists only if the process dies in between. W-1 pins one
case to a real loop-back, so the suite cannot pass over a dead feature if `gates.py` stops resetting
the target or retaining the source result; it found the target at `RUNNING`, which set the CB-3
condition. `test_runner_handover.py`'s mock run now carries `current_step`, as a real `PipelineRun`
always does.

`check_fr_coverage.py INT-US-04` passes **3 of 3**.

### CB-4 (2026-08-15)

`exposes` corrected per D-12; 3 unit tests; `tach check` green. Reintroducing one fictional name is
`KILLED` by 2 tests.

## Findings still open

- **Unmappable `context.yaml` changes.** `tests.py` reports e2e `selected NO tests` for CB-4:
  `src_relative()` returns `None` for any non-`.py` file (`_changed_file_mapping.py:37`), so a
  `context.yaml` change maps to no tier. The gate's `blocked_reason` reports this correctly, but a
  load-bearing `context.yaml` (it generates an enforced interface) is unmappable by the test gate.
  Not this SF's to fix.
- **Finding-flattening defined twice** — `_rule_payload` here and
  `interfaces/api/v1/validation.py::_rule_response`, which never lost the fields. Not a boundary
  violation (opposite dependency direction, different return types; `core.flow` cannot import
  `interfaces.api`), but a field set that must not drift. User decision at the pre-commit gate
  (architecture A-1..A-4; A-2: leave for now): consolidate into `assurance/validation` if a later
  boundary wants it.
- **Skill contradiction.** `phase-3-implement-tests.md` §3.1b says *"MANDATORY HITL YIELD… make ZERO
  further tool calls"*; its closing block says *"NO HITL GATE HERE… PROCEED IMMEDIATELY to Phase 4."*
  §3.1b was followed as the more specific. `TECH-019`'s class (contradictory gate orders).
- D-9 (`pipeline_engine_guide.md` records the grain) — not found in the guide as of 2026-09-25.
