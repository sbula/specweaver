# Walkthrough: `TECH-049` `FR-3` — the half that was never built

- **Ticket**: none. A defect in `TECH-049`'s delivered code, fixed on contact rather than filed
- **Kind**: bugfix · **DAL-C** · 2026-08-24

## What FR-3 says, and what shipped

> `FR-3` | Session baseline | The system SHALL run the full suite **once** per session and record the
> collected count **and the node id of every failing test**

The first half shipped. The second was captured and thrown away:

```python
# scripts/mutation.py:252 — the names exist
return Baseline(green=code == 0, failures=_mutate.killers(out), code=code)

# scripts/_session_record.py:268 — and here they stop
"failed": len(getattr(baseline, "failures", []) or []),
```

## How it survived a green ledger

`check_fr_coverage.py TECH-049` passes. `FR-3` is cited by **two** test files — and they pin
**opposite halves of the same requirement**:

| Test | Asserts | True? |
|---|---|---|
| `test_mutation_session.py::TestBaseline` — docstring *"records what failed, by node id"* | `run_baseline` captures the names | yes |
| `test_session_record.py::test_a_baseline_that_ran_reports_its_outcome` | the written record is **exactly** `{ran, green, failed}` | yes |

Both green, forever. The second **supplied** `failures=["tests/a.py::test_x"]` and asserted only the
count survived — it did not miss the requirement, it pinned its violation.

A citation count answers *is this FR mentioned*, never *is this FR met*. Recorded as an anti-pattern
in [`anti_patterns.md`](../../../architecture/06_lessons_and_future/anti_patterns.md).

## What it cost

Three consecutive nightly runs. `2026-08-22` and `2026-08-23` were dirty-tree artefacts;
**`2026-08-24` ran on clean commit `eeaa84ee` and was therefore real**. A red baseline voids every
verdict in the session — 145 of them that night — and the report said `1 failed` and nothing else.

The suite is green now: 8381 passed, and the blamed scope alone 36 passed. So the failing test is
flaky or bound to something about 03:00. There is a podman container in that night's journal at
03:00:45 — a lead, not a finding. **It stays unknown until it recurs, with a name attached.**

## The fix

| # | Change |
|---|---|
| 1 | `_baseline_block` writes `failures` beside `failed` — **written red**, the existing test pinned their removal |
| 2 | `render_summary` prints them under the *"meaningless while red"* line |
| 3 | Capped at ten in the **prose** with `... and N more`; the **JSON keeps every one** |
| 4 | `code` is recorded and shown — **found by the Phase 7.5 red/blue, the same defect one field over** |

### What the red/blue found

`killers()` returns `[]` when **pytest itself errored** — a broken conftest, a bad import — so a
collection failure produced `green: false, failures: []` and the report read `NOT GREEN (0 failed)`
while naming nothing. That is the undiagnosable state this boundary exists to close, reached by a
different route, and the fix would have shipped advertising a guarantee it did not give.

`Baseline` has carried `code` since it was written. `_baseline_block` dropped it exactly as it
dropped `failures`. Now: `NOT GREEN (0 failed, pytest exit 2)` — which separates *red with no names*
from *could not start*.

One thing it refuted rather than fixed: the capped prose list looked non-deterministic under
`-n auto`. `killers()` returns `sorted(set(...))`, and its docstring says *"sorted, so a run is
comparable with the next one."* Checked, not assumed.

Decisions, beside the facts they govern: `failed` **stays** rather than being derived
`[agreed 2026-08-24]` — removing it would touch the gate, the summary renderer and their tests, a
refactor wearing a bugfix's clothes, and one function writes both from one object so they cannot
drift. The prose cap of ten follows `check_decision_citations.py`'s existing shape rather than
introducing a number `[agreed 2026-08-24]`. **Schema stays at 1** — adding a key is additive and
every reader is in this repo `[agreed 2026-08-24]`.

## Results

| Tier | Scope | Passed |
|---|---|---|
| unit | module — `tests/unit/scripts` | 1,186 |
| integration | module — `tests/integration/scripts` | 38 |
| e2e | all | 256 |

`quality.py cb` 14 passed 1 skipped · `doc` 13/13 · `tach` ✅.

**`ruff format --check` caught this boundary**, exactly as the skill warns: `ruff check` was clean
while one test file was unformatted. It fired twice, both times on a test file. One command each; the 45 tests in the two files still pass.

## Probes — run inside the gate, not inherited

| Neutralised | Objections |
|---|---|
| the writer stops storing the names | 3 |
| the renderer stops printing them | 3 |
| the cap stops capping | **1** |
| `.get("failures") or []` → `baseline["failures"]` | 2 |
| the exit code stops being recorded | 2 |

**The cap has a single point of protection.** Carried here rather than shrugged at: one flaky or
skipped test away from none.

## The test that could not go red, and was probed instead

`--summary` replays records **off disk**, so it meets records written before this field existed —
including `.tmp/mutation_session.json` as it stands today. That path already worked, on
`.get("failures") or []`, so a test written now passes on its first run and asserts the present
rather than a contract.

Its validity rests on the fourth probe above, and that sentence is in the test's own docstring so
the next reader does not take it on trust.

## HITL gates

| Gate | Decision |
|---|---|
| dev Phase 1 red-flag | Nothing to ask — captured-then-discarded information, fix shape has in-repo precedent |
| dev Phase 2.5 task list | **Approved** |
| pre-commit Phase 2.8 | 0 architecture findings, 1 proposed story (the replay path). **Approved** |
| pre-commit Phase 3.1b | One test written, red impossible, probed instead. **Approved** |

No gate was skipped.

## Not fixed here, and named

- The failing test itself. This makes it diagnosable; it does not find it.
- `TECH-049` stays `COMPLETE`. Its design was **right** — the code was wrong — so nothing in it has
  become false and it is not edited.
