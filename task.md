# INT-US-04 SF-01 — CB-2: the table, its writer, its reader

**Plan**: `docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_sf01_implementation_plan.md` (APPROVED)
**FR**: FR-2 — persist rule results against `run_id` in a queryable table in the pipeline state DB
**Tiers**: unit (schema + store methods) · integration (the seam — this SF owns it, `ADR-003`)

**CB-1 delivered** in `e400cfdb`.

## ⚠ Plan correction needed before T5 — the approved write point is wrong

The plan says the writer goes at **the advance join point (`step_execution.py:474`), beside plan
hydration**. Verified today: that line is reached **only when `resolve_outcome` returns `PROCEED`**.

`resolve_outcome` (`step_execution.py:404-425`) returns:

| Situation | Return | Reaches `:474`? |
|---|---|---|
| step passed, advances | `PROCEED` | ✅ |
| **step failed → gate loops back** | `CONTINUE` | ❌ |
| step failed → gate retries | `CONTINUE` | ❌ |
| step failed, no gate | `RETURN` | ❌ |
| step parked (HITL) | `RETURN` | ❌ |

So the approved position would persist rule results for **passing** validate steps and silently
drop every failing one — precisely the findings that trigger loop-back and feed regeneration, and
precisely what FR-3 later replays. The table would fill up with clean runs.

**Proposed correction:** write immediately after `result = await execute_step(...)`
(`step_execution.py:465`), before `resolve_outcome`. Every step result passes there exactly once
per attempt, whatever the verdict. The run row already exists by then (persisted at `run_started`,
`runner.py:258`), so the `run_id` foreign key holds.

## Tasks

- [x] **T3** — `flow_validation_results` table + index on `run_id`; schema version row `3`.
      - src: `src/specweaver/core/flow/engine/store.py`
      - test: `tests/unit/core/flow/engine/test_validation_results_store.py` `[NEW]`
- [x] **T4** — `save_validation_results()` and `get_validation_results(run_id, *, step=None)`.
      - src: same · test: same
- [x] **T5** — wire the writer into the step loop at the corrected point; rule results only.
      - src: `src/specweaver/core/flow/engine/step_execution.py`
      - test: `tests/integration/core/flow/engine/test_validation_results_persistence.py` `[NEW]`

## Decisions carried from the plan

| # | Decision |
|---|---|
| D-2 → **D-11** | Append-only, autoincrement `id`, **one row per finding**: `(run_id, step_name, attempt, rule_id, finding_index)` + `message`/`line`/`severity`/`suggestion` columns |
| D-5 | **Rule results only.** `validate+spec` and `validate+code`; **not** `run_tests`, whose payload has no `rule_id`. Filter on `step_def.target in (SPEC, CODE)` — explicit, not duck-typed on the payload |
| D-7 | Never raises. Logs WARNING with the run id, and that path carries its own test |
| D-8 | Schema version row `3` |
| RB-5 | Rows carry the **validating step's own** attempt |
| RB-7 | Index on `run_id` — every query is by it, and `flow_artifact_events` sets the precedent |
| RB-9 | `get_validation_results` returns `list[dict[str, object]]`, matching `get_audit_log` |

**`attempt` source:** `run.step_records[step_idx].attempt`, **not** the in-memory `state.attempts`.
`TECH-033` moved the retry budget onto the durable record for exactly this reason — the in-memory
counter resets on resume. The precise value at the write point is subtle (the gate writes it
*after* the step runs), so it is **pinned by test at attempt 1 and attempt 2** rather than reasoned
about in prose.

## Red/Blue on this task list

| # | Finding | Severity | State |
|---|---|---|---|
| RC-1 | The approved write point drops every failing validate step (above) | **CRITICAL** | **approved** → write at `:465`; plan amended as D-10 |
| RC-2 | **The plan never says where `findings` go** at a per-rule grain | **CRITICAL** | **approved** → one row per finding, denormalized; plan amended as D-11. A rule with no findings still gets a row (`finding_index` NULL) so *"did S01 run and pass?"* stays answerable |
| RC-3 | Foreign key: does a fan-out **sub-run** have a row in `flow_pipeline_runs` to reference? | HIGH | **cleared** — sub-runs go through `PipelineRunner.run()` (`fan_out.py:65`), which persists its own row before any step executes |
| RC-4 | Writing before `resolve_outcome` — is the run row guaranteed present? | HIGH | **cleared** — persisted at `run_started` (`runner.py:258`), and `resume()` loads an existing row |
| RC-5 | Does an integration fixture with a failing validate step and a loop-back already exist? | MEDIUM | **cleared** — `test_generation_loopback_integration.py` is the precedent to follow |
| RC-6 | Same step writing twice in one attempt | LOW | not possible — one `execute_step` per loop iteration |

## Adversarial test matrix

| Bucket | Test |
|---|---|
| **Happy path** | A run with 3 rules writes 3 rows; `get_validation_results(run_id)` returns them with every column intact |
| **Boundary/edge** | Zero rules → zero rows, no crash. A rule with zero findings still writes its row. `step=` filter narrows correctly. A second attempt appends rather than overwrites, and both attempts remain readable |
| **Graceful degradation** | A locked/failing DB logs WARNING and does **not** raise (D-7). No store configured → writer is a no-op |
| **Hostile/wrong input** | A finding message with quotes/newlines/10k chars round-trips through SQLite unmangled; a `run_id` that does not exist is rejected by the foreign key rather than silently orphaned |

## Pre-commit gate

- [x] Phases 1–7.5 — architecture clean (B-1..B-4), gap analysis → V-1/V-2/V-3 approved and written

## Commit boundary

CB-2 of 4. **Done when:**
1. The writer neutralised to a no-op turns the **integration** test red (plan done-when).
2. A **failing** validate step's results are persisted — the regression the corrected write point
   exists for, and a test that would have passed at the planned position must fail there.
3. `tests.py cb INT-US-04 --all` green, pre-commit gate passed, HITL commit gate.
