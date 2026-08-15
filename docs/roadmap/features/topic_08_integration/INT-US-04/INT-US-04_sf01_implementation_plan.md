# Implementation Plan: Context-Aware Flow Orchestration Integration [SF-01: Core Flow DB Integration]

- **Feature ID**: INT-US-04
- **Sub-Feature**: SF-01 — Core Flow DB Integration
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_sf01_implementation_plan.md
- **Status**: APPROVED 2026-08-14

## Scope

Run-scoped persistence of validation output, and the resume gap that loses it. Decided by the user
on 2026-08-14 after `TECH-017` surfaced `INT-US-04` C1 as the audit's single open decision:
persistence **was** intended.

Three FRs, all amended or clarified in the design on the same day:

| FR | What it now says |
|---|---|
| FR-1 | Extract validation findings into `StepResult.output` **without loss** — including each `Finding`'s line, severity and suggestion |
| FR-2 | Persist rule results against `run_id` in a **queryable table in the pipeline state DB** (`flow_validation_results`) |
| FR-3 | Restore `context.feedback` **on resume**, so a resumed run regenerates against the same findings a same-session run would have seen |

**Out of scope, and not to be rediscovered:** the contract's *"sanitized"* clause (it maps to
`E-VAL-03`, unbuilt — `INT-US-04` C2's sanitization half stays `unproven` however this lands), and
cross-run history or any query/CLI surface over it.

## Phase 0 — Research Notes

### R-1. The interface this feature was designed against does not exist

`assurance/validation/context.yaml` declares `exposes: [ValidationRunner, ValidationResult,
RuleSeverity]`. **All three have zero occurrences anywhere in `src/`.** The real public surface is
`run_rules()` / `count_by_status()` / `all_passed()` over `RuleResult`, `Finding`, `Severity`,
`Status` in `assurance/validation/models.py`.

This explains the contract's wording, and `TECH-017`'s finding that *"`ValidationResult` does not
appear in `src/`"*. The design was written against a **declared** interface rather than the code.
**Every reference in this plan is to `RuleResult` / `Finding`.**

Measured across the tree: 7 modules have stale `exposes`, but `assurance/validation` is the only one
at **3 of 3**. Nothing enforces the field — `tach.toml` does not read it, and no script does.

### R-2. Validation output is ALREADY persisted — opaquely, and in the other database

`StateStore.save_run` serializes `[r.model_dump() for r in run.step_records]` into
`flow_pipeline_runs.step_records` as one JSON blob (`store.py:175`). `StepResult.output` rides
along, so rule results already survive a process restart. What does not exist is any **queryable**
form: no `rule_id`, `status` or `severity` column anywhere, and it lives in `pipeline_state.db`,
not the Config DB the contract names.

### R-3. FR-1 is built and lossy at a precise line

`handlers/validation.py:108-114` builds `output` as
`{"results": [{"rule_id", "status", "message"} …], "total", "passed"}`. **`Finding` is dropped
entirely** — zero occurrences of `findings` in that file. Line numbers, severities and suggestions
are computed by the rules and discarded at the handler boundary.

### R-4. FR-3's injection is built; only the fetch is missing

`gates.inject_feedback` (`gates.py:146`) writes
`context.feedback[to_step] = {"from_step": …, "findings": result.output}`, called from
`step_execution.py:305` on the `loop_back` verdict. `generation.py:85-87` and `draft.py:36-37`
**pop** it into the next prompt. This works, in memory, within one process.

### R-5. The defect: `context.feedback` never reaches a store

`feedback` is a plain field on `RunContext` (`run_context.py:157`). Neither `store.py` nor
`hydration.py` references it. `resume()` calls `rehydrate_from_records` which rebuilds
`plan_context` and **nothing else**, so a resumed run regenerates with no findings and repeats the
mistake validation caught.

### R-6. This exact bug class has been fixed twice already on this exact code path

Both fixes are in the loop-back branch of `gates.py`, and both are load-bearing here:

* **`TECH-021`** — the failing step's result was discarded on loop-back (`status=RUNNING`,
  `result=None`), so a human resuming *"had no record of why the later step failed"*. Fixed by
  retaining `run.step_records[step_idx].status/result` (`gates.py:222-223`).
* **`TECH-033`** — the retry budget lived only in memory, so *"a resume restarted it at zero"*.
  Fixed by persisting `attempt` into the step record (`gates.py:229`).

**This matters more than it looks.** `TECH-021` already persists exactly the payload
`inject_feedback` injects — the failing step's `result.output`. The data FR-3 needs is *already in
the store*; what is missing is the replay.

Note also `gates.py:232-233`: the loop **target's** record is reset to `PENDING` / `result=None`.
That, plus `run.current_step`, is the state a replay must key on.

### R-7. The hydration pattern this must mirror, and its stated invariant

`hydrate_plan_context` (`hydration.py:88`) is documented as *"the single hydration point: the runner
calls it after a step advances, and `resume()` replays it over persisted step records, so the live
path and the cross-session path cannot drift apart."* It never raises; a malformed artifact degrades
to a WARNING.

It also carries a warning this plan must obey (`hydration.py:110-115`): `default=str` is **not
optional**, because `StateStore` persists with exactly those semantics — without it, an output
carrying a `Path`/`set` raises on the LIVE path but hydrates fine on the RESUME path. *"Sharing this
function is only half the guarantee; the serialization semantics must match too."*

Join points already established: `step_execution.py:474` (advance — both gate and no-gate paths) and
`runner.py:216` (resume).

### R-8. Adding a table needs no data migration

`_ensure_schema` runs `conn.executescript(_STATE_SCHEMA_V2)` on **every** construction, and every
statement is `CREATE TABLE IF NOT EXISTS`. A new table therefore appears on existing databases
automatically. The `flow_state_schema_version` row and the v1→v2 `ALTER TABLE` path exist for
**column** additions, which this is not.

### R-9. No new dependency, and NFR-1's original wording was doubly wrong

`StateStore` is raw `sqlite3` in WAL mode (stdlib), not SQLAlchemy. The design's original NFR-1
*"DB writes must use async session execution"* assumed `FlowRepository`/Config DB; there is no
session here and nothing to await. Amended 2026-08-14. `pyproject.toml` needs no change.

### R-10. Boundaries permit the obvious import — and the better design needs none

`tach.toml:46` already lists `specweaver.assurance.validation` in `core.flow`'s `depends_on`, and
the `assurance/validation` core imports nothing from `core.flow` (only its `interfaces/` submodule
does, lazily, and that is a separate tach module). So importing `RuleResult` into the engine is
legal.

**It should still not be done.** `handlers/validation.py` already flattens rule results to
primitive dicts before they reach `StepResult.output`; the store can persist those primitives and
import nothing. Fewer edges, and the store stays a store.

### R-11. Test precedents to follow rather than invent

* `tests/unit/core/flow/engine/test_runner_rehydration.py` — the `INT-US-21` FR-3 proof, including
  the boundary cases this plan inherits (empty records, more records than steps, reordered pipeline).
* `tests/unit/core/flow/engine/test_engine_store.py` — schema/migration test shape.
* `tests/integration/core/flow/engine/test_pipeline_state_persistence.py` and
  `test_rehydration_integration.py` — the integration tier already exists for exactly this seam.
* `tests/unit/core/flow/engine/test_retry_budget_across_resume.py` — `TECH-033`'s across-resume
  proof, the closest existing analogue to FR-3's test.

## Phase 3 — Architecture Verification

| Check | Result |
|---|---|
| Layer placement | All changes sit in `core/flow/engine/` and `core/flow/handlers/`, both inside the existing `flow` module. No new module, no new `context.yaml`. |
| Dependency direction | Unchanged if R-10 is followed (primitives only). `tach check` is green today and must stay green. |
| Circular imports | None introduced. `store.py` imports only `commons.json` and `engine.state`. |
| Archetype fit | `flow` is `orchestrator`; persisting its own run state is squarely its concern. `pipeline_state.db` is already its private store. |
| Config/state separation | Honoured. `store.py:7` declares the state DB *"isolated from the configuration database"*; per-run validation results are runtime state. This is why FR-2 was amended away from the Config DB. |
| Schema evolution | New table via `CREATE TABLE IF NOT EXISTS` (R-8). Version bump to 3 is optional and recommended for traceability, not required for correctness. |

## Decisions taken at the Phase 4 gate (2026-08-14)

**D-1 — Replay restores; the table gets a reader.** `FR-3` replays feedback from persisted step
records, mirroring `hydrate_plan_context`'s stated invariant (R-7) so the live and resumed paths
cannot drift. `flow_validation_results` serves `FR-2`'s queryable-persistence claim and ships with
`StateStore.get_validation_results(run_id, *, step=None)`, exercised at integration tier.

Two deliverables, honestly labelled: **replay fixes the defect, the table closes the claim.** The
reader is not decoration — without it the table has no in-code consumer, and a write-only table is
the kind of thing a later tidy-up deletes. It is also what any future history feature builds on.

Rejected: making the table the restore path. It would be load-bearing, but at the cost of two
persistence mechanisms for one payload — precisely the drift `hydration.py:110-115` warns about.

**D-2 — Append-only grain: autoincrement `id` plus `(run_id, step_name, attempt, rule_id)`.**
Matches `flow_audit_log`'s existing shape and never loses history. Overwrite-per-rule was rejected
because a retried run's earlier failures would vanish — the information `TECH-021` was filed to stop
losing (R-6). `attempt` is a real column rather than inferred from insertion order, which nothing
enforces.

**D-3 — `FR-1` carries the full `Finding` list, and the cost is measured, not guessed.**
`message`, `line`, `severity`, `suggestion` per finding, honouring *"without loss"* literally.
**The implementer MUST record the measured `step_records` blob-size delta on a real run in this
plan**, and only propose a cap if that measurement shows a problem. A silent cap is the kind of
truncation that reads as completeness later; if one is ever needed, `FR-1`'s wording changes with it.

**D-4 — the stale `context.yaml` (R-1) is fixed in this sub-feature.** `assurance/validation`'s
`exposes` becomes the real surface: `run_rules`, `count_by_status`, `all_passed`, `RuleResult`,
`Finding`, `Severity`, `Status`. Three wrong lines that directly produced this design's wrong `FR-1`;
`AD-2` and the no-inflation rule both point at fixing in place.

**Explicitly NOT widened:** the other six modules with stale `exposes` are reported (R-1) and left.
Sweeping them, and adding the check that would stop them regrowing, is a separate concern from
persisting validation output.

### Decided by proposal, no gate needed

| # | Decision |
|---|---|
| D-5 | **Rule results only.** Both `validate+spec` (`validation.py:108`) and `validate+code` (:245) persist; `run_tests` does not — its payload has no `rule_id`, and forcing it in would make the table mean two things. |
| D-6 | **Replay keys on the loop target still being `PENDING`.** `gates.py:232-233` resets the target's record to `PENDING`/`result=None`, so that flag distinguishes *feedback pending* from *already consumed*. Without it a resumed run could re-apply a stale round's findings — the bug `generation.py:80-84` guards against in-session by popping. |
| D-7 | **Persistence never raises.** Matches `hydrate_plan_context` and `flush_telemetry`. Logs at WARNING with the run id, and that path carries its own test — a degradation path with no test is how `TECH-032`'s vacuous successes happened. |
| D-8 | **Schema version bumps to 3.** Not required for correctness (R-8), done so the recorded version reflects reality. |
| D-9 | **`docs/dev_guides/pipeline_engine_guide.md` records the table's grain**, so the next reader finds it where they look for engine persistence rather than in this plan. |

### Deferred, and NOT blocking implementation

| # | Item |
|---|---|
| Q-11 | Whether `INT-US-04`'s base contract flips `⬜ Pending` → `✅` when SF-01 lands. It closes the persistence half; C2's *"sanitized"* stays `unproven` against the unbuilt `E-VAL-03` regardless. A status decision, and the user's, taken at delivery rather than now. |

## Commit boundaries

Four, each independently committable, each naming its tier per `ADR-003`.

### CB-1 — FR-1: stop dropping `Finding`

Widen the `results` payload in `handlers/validation.py` at :108 and :245 to carry each rule's full
`Finding` list (D-3). **Unit** tier — one module's behaviour, no seam.

**Done when:**
1. The test **kills a mutant**: drop the `findings` key from the payload builder and the test goes
   red. A test that still passes is asserting on `total`/`passed`, not on what FR-1 promises.
2. **The measured `step_records` blob-size delta on a real run is recorded in this plan** (RB-6). An
   unrecorded measurement blocks this boundary; a cap is only proposed if the number justifies one,
   and `FR-1`'s wording changes with it if so.

#### CB-1 measurement (D-3 / RB-6) — recorded 2026-08-14

Method as pinned: `len(json.dumps([rec.model_dump()], default=str))` for one `validate_spec` step
record — the expression `StateStore.save_run` uses (`store.py:175`) — same spec, payload with and
without the `findings` key. Script: `.tmp/measure_blob.py` (gitignored; the numbers are the record,
not the script).

| Spec | Rules | Findings | Before | After | Delta |
|---|---|---|---|---|---|
| `tests/fixtures/good_spec.md` | 12 | 3 | 1 445 B | 2 262 B | **+817 B (+56.5%)** |
| `specs/TestComponent_spec.md` | 12 | 5 | 1 456 B | 2 509 B | **+1 053 B (+72.3%)** |
| deliberately weasel-worded spec | 12 | 10 | 1 382 B | 3 110 B | **+1 728 B (+125.0%)** |

Linear at roughly **170 bytes per finding**, plus about 15 bytes per rule for the empty-list key
even when a rule finds nothing.

**No cap proposed.** The percentage looks alarming and the absolute does not: the worst case
measured is a **3.1 KB** step record, and a pathological 100-finding spec would reach ~19 KB — far
inside anything SQLite or the loop-back prompt cares about. `FR-1`'s *without loss* therefore stands
as written; had a cap been needed, the FR's wording would have had to change with it (D-3).

#### CB-1 outcome (delivered 2026-08-14)

`_rule_payload()` carries all four `Finding` fields; both call sites use it. 8 unit tests.

**Two deviations from the plan, both upward:**

1. **A second shared helper, `_validation_output()`.** `TECH-037`'s duplication gate failed *after*
   the first extraction: collapsing the two identical `results` comprehensions **re-keyed** the
   remainder and exposed an 11-line clone underneath — the same `output` dict and `StepResult`
   shape in both handlers. Pre-existing, and surfaced for the first time by removing the layer
   above it. Fixed per the inherited-failures rule; duplication baseline re-frozen 123 → 121.
2. **Two extra unit tests (U-1, U-2)** from the pre-commit Phase 2 gap analysis: multi-rule order
   and count, and the sibling tallies surviving the widening. Both probed to a killed mutant.

**Mutants run:**

| Mutant | Result |
|---|---|
| drop the `findings` key | `KILLED` ×8 |
| drop `suggestion` (partial loss) | `KILLED` ×3 |
| reverse rule order | `KILLED` ×2 |
| `passed` counts only `PASS` (excludes WARN/SKIP) | `KILLED` ×1 — **single point of protection** |
| `f.severity.value` → `f.severity` | `SURVIVED` — **equivalent**, `Severity` is a `StrEnum` |

The equivalent mutant earned its keep: it exposed a **vacuous assertion in the new test** (`"Severity."
not in blob` can never fail for a `StrEnum`), replaced with a pin on the premise that can —
`issubclass(Severity, str)`. The source docstring claiming `.value` was load-bearing was corrected
with it.

**Gate results** (all re-run fresh inside the pre-commit gate, nothing carried over):

| Gate | Result |
|---|---|
| `tests.py cb INT-US-04 --all` | unit 6 107 · integration 58 · e2e 15 — **6 180 passed**, 11 skipped, DAL-D (most critical of `D-FLOW-01`, `E-FLOW-01`, `E-VAL-01`) |
| `quality.py cb` | 13/13 — ruff, `ruff format --check`, mypy, complexipy, tach, file sizes, suppressions, class health, cycles, duplication, coupling, conventions, test guards |
| `quality.py doc` | 9/9 |
| `useless_asserts`, `test_basenames` | green (pulled forward to Phase 2 per §2.5b) |

**Widening was necessary and is worth recording.** `tests.py cb INT-US-04` selects **integration and
e2e only — no unit tier**, because `INT-US-04` is an integration story. CB-1's change is unit-tier
by `ADR-003` (behaviour of one module), so the story's own gate would have passed it **unverified**.
Run with `--all` it failed immediately: the FR sweep baseline had gone stale at 242 because the new
`Proves:` tag cited a previously uncited FR. Re-frozen to 241.

That is the tension the tier rule creates and does not resolve: `tests.py`'s profile says an INT
story wanting a unit test is a signal that the capability underneath shipped incomplete — which is
*exactly* what R-3 found. The signal was right; the gate still would not have run the test.

**HITL gates — every one, and what was decided:**

| Gate | Presented | Decision |
|---|---|---|
| impl-plan Phase 4 | 4 questions: table's purpose, grain, `Finding` depth, stale `context.yaml` | All four recommendations accepted → D-1..D-4 |
| impl-plan Phase 5 | Consistency + 3 Red/Blue cycles, 11 findings, 1 CRITICAL (`RB-1`) | Approved; plan `APPROVED`, `Impl Plan ✅` |
| dev Phase 2 | Task list + 6 Red/Blue findings on it | Approved |
| pre-commit Phase 2 | Architecture (A-1..A-4) + coverage matrix + 2 proposed stories | **U-1 and U-2: write both. A-2: leave for now** |
| pre-commit Phase 3 | The two tests, both probed to a killed mutant | Approved |

**No gate was skipped or auto-approved.**

**Skill defect found, not fixed here.** `phase-3-implement-tests.md` contradicts itself: §3.1b says
*"MANDATORY HITL YIELD… make ZERO further tool calls"* while the closing block of the same file says
*"NO HITL GATE HERE… PROCEED IMMEDIATELY to Phase 4."* §3.1b was followed as the more specific
instruction. This is `TECH-019`'s class (contradictory gate orders) and belongs to whoever reconciles
it, not to this boundary.

**Recorded, not acted on** (user decision at the Phase 2 gate): the finding-flattening now exists in
two places — here and `interfaces/api/v1/validation.py::_rule_response`, which never lost the fields.
Not a boundary violation (opposite dependency direction, different return types; `core.flow` cannot
import `interfaces.api`), but a field set defined twice that must not drift. Consolidating it into
`assurance/validation` is the option if a later boundary wants it.

> [!IMPORTANT]
> **CB-2 amended 2026-08-14, before implementation, on two findings from its task-list Red/Blue.**
> Both were errors in this plan as approved, found by reading the code the plan named.
>
> **D-10 — the write point moves to `step_execution.py:465`, before `resolve_outcome`.** CB-2 below
> said *"the advance join point (`:474`), beside plan hydration"*. That line is reached **only when
> `resolve_outcome` returns `PROCEED`**. A validate step that fails and loops back returns
> `CONTINUE`; one that fails without a gate, or parks for HITL, returns `RETURN`. The planned
> position would have persisted rule results for **passing** steps and silently dropped every
> failing one — the findings that trigger loop-back, feed regeneration, and are exactly what `FR-3`
> replays. Writing straight after `execute_step()` catches every result once per attempt whatever
> the verdict; the run row already exists there (`runner.py:258`), so the foreign key holds.
>
> Symmetry with `hydrate_plan_context` was the reason for the original position, and it was the
> wrong reason: hydration *should* only run on advance, because a failed step has no plan to
> hydrate. Persistence has the opposite requirement.
>
> **D-11 — the grain becomes one row per FINDING**, not per rule:
> `(run_id, step_name, attempt, rule_id, finding_index)` with `message`, `line`, `severity` and
> `suggestion` as real columns. D-2's per-rule grain left findings nowhere to go but a JSON column —
> which is the opaque blob `CB-1` had just rescued them from, one layer down, in a table whose whole
> claim is that it is **queryable**. Denormalized rather than two tables: a join for a feature whose
> only consumer today is a test is work without a reader (`KISS`), and the redundancy is bounded by
> the ~170 bytes/finding already measured.
>
> **A rule that produced no findings still gets one row**, with `finding_index` and the four finding
> columns `NULL`. Otherwise passing rules vanish from the table entirely and *"did S01 run, and did
> it pass?"* — the first question anyone asks of validation history — becomes unanswerable.

### CB-2 — FR-2: the table, its writer, its reader

`flow_validation_results` added to `_STATE_SCHEMA_V2` with an index on `run_id` (RB-7), version row
3 (D-8), plus `save_validation_results()` and `get_validation_results(run_id, *, step=None)`
returning `list[dict[str, object]]` (RB-9). Written from the advance join point
(`step_execution.py:474`), beside plan hydration, so both persistence paths share one trigger.
Rows carry the **validating step's own** `attempt` (RB-5). Rule results only — not `run_tests` (D-5).

**Unit** for schema and store methods; **integration** for the seam. Per `ADR-003` this SF owns that
integration test; no later story will write it.

**Done when** the writer neutralised to a no-op turns the integration test red.

#### CB-2 outcome (delivered 2026-08-14)

`flow_validation_results` (one row per finding, index on `run_id`, schema v3), plus
`save_validation_results` / `get_validation_results` and `persist_validation_results` in the step
loop. 18 unit + 4 integration tests.

Mutants: writer as a no-op `KILLED`; **call moved back to the originally planned `:474`
`KILLED`** — empirical proof D-10's correction was necessary; `except Exception` narrowed
`KILLED ×1` (single point of protection).

Three tests added at the pre-commit gate for branches the seam cannot reach — the never-raises path
D-7 had promised and not delivered, a malformed `results` payload, and the `attempt` fallback.
`useless_asserts` rejected the first draft of one (`assert mock.called` cannot fail); tightened to
`assert_called_once`.

Touched: three `version == 2` pins in `test_engine_store.py` (the current version is 3),
FR-sweep baseline 241 → 240.

### CB-3 — FR-3: restore feedback on resume

`replay_feedback(pipeline, run, context)` in `hydration.py`, called from `rehydrate_from_records`,
carrying `default=str` semantics (R-7).

The replay condition is a **conjunction** (RB-4), not the single `PENDING` check first drafted:

1. the gate's `loop_target` names the step at `run.current_step`;
2. that target's record is `PENDING` with `result=None` (`gates.py:232-233`);
3. the **source** step's record carries a `result` whose status is not `PASSED` — checkable only
   because `TECH-021` stopped discarding it (R-6).

Where two gates share a target, the **highest-indexed** eligible source wins (RB-2) — the same rule
`rehydrate_from_records` already uses. Feedback is written under the **target** step's name (RB-3),
because that is what `generation.py:87` pops.

**Integration** tier, and the boundary where a red means something: write the test after CB-2's
interface exists and before the restore behaviour does. **Record the red and its reason** — the one
piece of evidence a `Proves:` tag can never supply.

**Done when** deleting the `replay_feedback` call from `rehydrate_from_records` turns the test red.
This is the mutant that matters most: the entire defect is an absent call, so a test that survives
its removal is proving nothing.

#### CB-3 outcome (delivered 2026-08-15)

`replay_feedback` in `hydration.py`, called from `rehydrate_from_records`, reusing
`GateEvaluator.inject_feedback`. 11 unit + 4 integration tests. Done-when mutant — deleting the
call — `KILLED`.

**The red was recorded, and the first attempt at it was wrong.** The integration test initially
failed because session 1 ran to completion, so there was nothing to resume: in one process a
loop-back is immediately followed by re-execution, and the paused-at-target state exists only if
the process dies between. Rebuilt to construct that state directly, it then failed for the right
reason — *"the regenerating step was handed NO feedback on resume"*.

**W-1 changed the implementation.** It was proposed at the pre-commit gate to stop the test proving
its own fixture: every other case hand-builds the interrupted run, so if `gates.py` stopped
resetting the target or retaining the source result, they would pass over a dead feature. Pinned to
a real loop-back, the observed target status is **`RUNNING`**, not `PENDING` — `mark_step_running`
fires and is persisted. There are therefore **two reachable crash points**, and the condition as
planned (RB-4, `PENDING` only) would have left a run that died mid-regeneration to resume blind.
The discriminator is `result is None`; status now accepts `PENDING` or `RUNNING`.

Also completed `test_runner_handover.py`'s mock run with `current_step`, which a real `PipelineRun`
always carries — the stand-in was less constrained than the type it stood in for.

`check_fr_coverage.py INT-US-04` now passes **3 of 3**.

### CB-4 — D-4/RB-1: correct `assurance/validation`'s declared interface

`exposes` becomes the real surface. Not documentation tidying — `tach_sync` regenerates
`tach.toml`'s `[[interfaces]]` from this field, so today a sync would replace 12 correct names with
3 fictional ones and break every import from the module (RB-1).

**Done when:** `tach check` is green after the edit, and a **unit** test asserts every name in that
`exposes` resolves to a real symbol — without it the drift returns on the next hand edit.

## Proposed Changes

| File | Tag | Change |
|---|---|---|
| `src/specweaver/core/flow/handlers/validation.py` | `[MODIFY]` | Widen the `results` payload at **:108** (`validate+spec`) and **:245** (`validate+code`) to carry each rule's full `Finding` list (D-3) |
| `src/specweaver/core/flow/engine/store.py` | `[MODIFY]` | `flow_validation_results` in `_STATE_SCHEMA_V2` + index on `run_id`; `save_validation_results()`, `get_validation_results()`; version row 3 (D-8) |
| `src/specweaver/core/flow/engine/hydration.py` | `[MODIFY]` | `replay_feedback(pipeline, run, context)`, called from `rehydrate_from_records` (D-1) |
| `src/specweaver/core/flow/engine/step_execution.py` | `[MODIFY]` | Call the validation-results writer at the advance join point (**:474**), beside `hydrate_plan_context` |
| `src/specweaver/assurance/validation/context.yaml` | `[MODIFY]` | `exposes` → the real surface (D-4 / RB-1) |
| `tests/unit/core/flow/handlers/test_validate_spec_findings.py` | `[NEW]` | FR-1 |
| `tests/unit/core/flow/engine/test_validation_results_store.py` | `[NEW]` | FR-2, store methods + schema |
| `tests/integration/core/flow/engine/test_validation_results_persistence.py` | `[NEW]` | FR-2 seam |
| `tests/integration/core/flow/engine/test_feedback_replay_across_resume.py` | `[NEW]` | FR-3 |
| `docs/dev_guides/pipeline_engine_guide.md` | `[MODIFY]` | Record the table's grain (D-9) |

No new module, no new `context.yaml`, no `pyproject.toml` change (R-9).

## Red/Blue Team Review

Three cycles. Findings incorporated above and below; the plan as first drafted did not survive
contact with any of RB-1 through RB-4.

### RB-1 (CRITICAL) — the stale `context.yaml` is a live landmine, not untidiness

`tach.toml` carries 20 `[[interfaces]]` blocks, and `tach_sync.sync_tach_toml`
(`workspace/project/tach_sync.py:53-63`) **generates them from `context.yaml`'s `exposes`**. The
block for `specweaver.assurance.validation` currently lists the **real** surface — `models`,
`models.RuleResult`, `models.Status`, `executor`, `loader`, … — and `ValidationResult` appears
**nowhere** in `tach.toml`.

So `tach.toml` is right and `context.yaml` disagrees with it *and* with the code. **Running
`sw`'s tach sync against this repo today would replace a correct 12-name expose list with three
names that do not exist, and tach enforces interfaces — every import from `assurance.validation`
would start failing.**

D-4 therefore defuses a regeneration hazard. **Blue:** accepted and promoted. CB-4's done-when adds
`tach check` green *after* the edit, and a test asserting every name in that `exposes` resolves to a
real symbol — otherwise the same drift returns the next time someone edits it by hand.

### RB-2 (HIGH) — two gates can loop back to the same target

`inject_feedback` keys `context.feedback` by **`to_step`**. A pipeline with two gates whose
`loop_target` is the same step (`run_tests` → `generate_code` and `validate_code` → `generate_code`
is the shape `sw implement` already has) gives the replay two candidate sources and no rule for
choosing. **Blue:** replay the **highest-indexed** source step that satisfies RB-4's conditions —
the same "later index wins" rule `rehydrate_from_records` already uses
(`test_runner_rehydration.py::test_later_index_wins`). Stated in CB-3 and given its own test.

### RB-3 (HIGH) — the replay must write under the TARGET step's name

`generation.py:87` pops `context.feedback[step.name]` where `step` is the step **about to run**.
`inject_feedback` writes under `to_step`. A replay that keys on the failing step's name would
persist a dict nothing ever reads, and every test asserting "feedback was restored" would pass.
**Blue:** pinned explicitly in CB-3, and the test asserts the *consuming* handler sees it, not that
the dict is non-empty.

### RB-4 (HIGH) — "target is `PENDING`" is not a loop-back signal on its own

Every step record starts `PENDING`. D-6 as first written would replay feedback on any resume whose
current step happens to be a gate target, including runs that never looped back. **Blue:** the
condition is a **conjunction** — the target record is `PENDING` **and** the source step's record
carries a `result` **and** that result is not `PASSED`. `TECH-021` is what makes the second and
third checkable (R-6); before it, the failing result was discarded.

### RB-5 (MEDIUM) — which `attempt` does a row carry?

D-2's key includes `attempt`, but two step records are in play. **Blue:** the **validating step's
own** `attempt`, since the row describes that step's execution. Stated in CB-2.

### RB-6 (MEDIUM) — D-3's measurement had no failing condition

"The implementer MUST record the measured delta" is a suggestion unless something fails without it.
**Blue:** moved into CB-1's done-when, where an unrecorded measurement blocks the boundary.

### RB-7 (MEDIUM) — the table needs an index

`flow_artifact_events` indexes `artifact_id`. Every query here is by `run_id`. **Blue:** index it.

### RB-8 (MEDIUM) — `validate+code` rows can never become feedback

`validate_code` is report-only behind a `CONTINUE` gate (`workflows/implementation/interfaces/cli.py`),
so it never loop-backs and its findings never reach `inject_feedback`. Its rows serve **FR-2 only**.
**Blue:** stated, so nobody later "fixes" the absence of code-rule findings in a regeneration prompt.

### RB-9 (LOW) — return type

`get_validation_results` returns `list[dict[str, object]]`, matching `get_audit_log`'s existing shape.

### RB-10 (LOW) — fan-out sub-runs

`fan_out.py` gives sub-runs isolated `RunContext`s. Replay is defined for the run being resumed only;
sub-run feedback is **out of scope** and named as such.

### RB-11 (LOW) — a crash between the two writes

`runner._persist(run)` (`step_execution.py:399`) precedes the validation-results write (:474), so a
crash between them leaves a run row with no result rows. Acceptable under D-7 (never raise,
append-only), and stated rather than discovered later.

## Verification Plan

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

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | The table ships write-only and is deleted by a later tidy-up | Q-2: ship a reader and prove it at integration tier |
| R-2 | Replay re-applies consumed feedback | Q-6: key on the target record being `PENDING`; test the already-consumed case explicitly |
| R-3 | Widened `output` (CB-1) inflates every persisted run record | Q-3: measure the blob delta on a real run and state it in the plan before capping |
| R-4 | Live and resumed paths drift, the exact failure `hydration.py` warns about | Single replay function called from both paths, mirroring `hydrate_plan_context`; `default=str` on both sides |
| R-5 | Scope creep into cross-run history | Named out of scope above; Q-2's reader is `run_id`-scoped by signature |

## Phase 5 — Consistency Check

**5.0 Design coverage.** All three FRs are carried (CB-1/CB-2/CB-3) and each names its tier. NFR-1
(non-blocking writes) is met — `StateStore` is sync `sqlite3` in WAL mode and writes are
`INSERT`-only (R-9); its original *async session* wording was amended 2026-08-14. NFR-2
(architecture compliance) is verified in §Phase 3 and re-checked by CB-4's `tach check`. NFR-3
(compatibility) is CB-2's requirement that `test_mcp_flow_e2e.py` and every existing pipeline YAML
keep working without modification; R-8 is why no data migration threatens that.

**5.1 Open questions.** All decisions are resolved and documented inline (D-1..D-9, RB-1..RB-11).
One item is deferred and explicitly non-blocking: **Q-11**, whether `INT-US-04`'s base contract
flips `⬜ Pending` → `✅` on delivery. It is a status decision for the user at delivery time, and no
code depends on it.

**5.1a Agent handoff risk.** A fresh agent starting from this document alone would most likely
stumble on four things, each now pinned rather than left to inference:

* **That the table is not the restore path** (D-1). The obvious reading of "persist validation
  output, restore it on resume" is one mechanism; this plan deliberately uses two, and says why.
* **The feedback key** (RB-3). Writing under the failing step's name produces a dict nothing reads,
  and every "feedback restored" assertion still passes. Named explicitly, with the consuming-handler
  assertion required.
* **The replay condition** (RB-4). `PENDING` alone looks sufficient and is not.
* **`ValidationResult` does not exist** (R-1). The design and contract both name it; an agent
  trusting them would write against a type with zero occurrences in `src/`.

**5.2 Architecture and future compatibility.** No circular imports: `store.py` imports only
`commons.json` and `engine.state`, and D-1's primitive-only payload means no new edge at all (R-10).
`consumes`/`forbids` unchanged in every affected `context.yaml`. Forward fit: cross-run history —
the natural next feature — builds directly on CB-2's append-only grain and `get_validation_results`;
`E-VAL-03` (sanitization) would wrap the payload CB-1 widens; `INT-US-04` SF-09's declarative routing
consumes `RunContext`, untouched here.

**5.2a Principles.** *DDD* — validation results are flow's own run state, persisted in flow's own
store; the ubiquitous language becomes `RuleResult`/`Finding`, correcting a term the design invented
(R-1). *KISS* — the table needs no migration (R-8) and no dependency (R-9); the one deliberate
complexity is D-1's two mechanisms, justified against the drift alternative. *DRY* — replay reuses
`inject_feedback` rather than re-implementing the injection shape, mirroring how
`rehydrate_from_records` reuses `hydrate_plan_context`. *Hexagonal* — `StateStore` stays the
adapter, handlers stay policy, and no domain type crosses into the store. *Separation of concerns* —
the store gains persistence methods only; the replay decision lives in `hydration.py` with the other
resume-time reconstruction.

**5.2b Red/Blue.** Three cycles, 11 findings, one CRITICAL — see §Red/Blue Team Review. Cycle 3
produced no new findings above LOW, which is the stated stopping condition.

**5.3 Internal consistency.** Every file in §Proposed Changes carries a `[NEW]`/`[MODIFY]` tag. The
schema change is reflected in both `_STATE_SCHEMA_V2` and the version row (D-8). Every function
named here — `save_validation_results`, `get_validation_results`, `replay_feedback` — appears in
§Verification Plan. No `_schema.py`/mixin split applies: this is the state DB, which owns its schema
inline in `store.py`.

**5.3a Code detail limit.** The plan contains no new-code blocks. Every code reference is either an
exact signature or a cited line from existing code (a research finding), or an ordered list of
conditions (CB-3's conjunction). Nothing here is paste-ready; the implementation is the `dev`
skill's job, test-first.

## Session Handoff

Phases 0–5 complete. Preconditions verified green in code (`check_story_preconditions.py INT-US-04`,
exit 0, 6 passed). Four gate decisions taken by the user (D-1..D-4); three Red/Blue cycles produced
11 findings, one CRITICAL (RB-1). **Awaiting the Phase 5 HITL approval.** On approval: `Status:
APPROVED`, `Impl Plan ✅` for SF-01 in the design's Progress Tracker, then trigger the `dev` skill at
CB-1.
