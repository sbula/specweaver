# Implementation Plan: The Two Foundations Nobody Wrote Down

- **Feature ID**: TECH-054
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-054/TECH-054_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-054/TECH-054_implementation_plan.md
- **Status**: APPROVED (2026-08-16)

**FRs owned: FR-1 (CB-1), FR-2 (CB-2).** Two commit boundaries, one journey each.

Both FRs are **consequences** of the journeys rather than inputs to them. The ticket set out to
write two falsifiable claims about capabilities that had none; each claim failed on first contact,
and the requirement is the repair. That order is the whole argument for journey proofs over
reverse-engineered designs, so it is recorded rather than tidied away.

## CB-1 — `D-FLOW-01`: a pipeline runs and its state survives a resume

`tests/e2e/core/flow/test_resume_after_failure_journey_e2e.py`, four subprocesses. A two-step bash
pipeline loaded **from a YAML path**: step 1 appends to `marks.txt`, step 2 exits 3 until a sentinel
appears. Run, fail, create the sentinel, `sw resume` — and `marks.txt` must still be one line long.

`StateStore.get_latest_resumable_run(project)` replaces the loop over `list_bundled_pipelines()` in
`_resolve_resumable_run`. The status filter goes **inside** the SQL: applied afterwards it would
select the newest run of any kind and then discard it, reporting nothing to resume while a parked
run waits.

### Proof, per claim

| Claim | Proven by | Tier |
|---|---|---|
| FR-1, the query | `test_resumable_run_discovery.py::TestGetLatestResumableRun` (7 cases) | unit |
| FR-1, end to end | `test_resume_after_failure_journey_e2e.py` (2 cases) | e2e |

**No integration tier here.** The seam between the CLI and the store is one call with no adapter
between them, and the e2e crosses it for real in a subprocess; an integration test would assert
that a function called the function it calls.

### Two findings worth keeping

**The first draft passed vacuously.** `sw resume` exits **0** when it finds nothing to resume, so
*"exit 0 and step 1 ran exactly once"* is satisfied perfectly by a resume that never happened. Step
2 now writes its own trace file and the journey asserts on that.

**Coverage clustered on the mechanism, not the path to it.** Neutralising persistence itself
(`run.current_step = 0` before the loop) is killed by **14 tests across three tiers**. Discovery had
nothing: the bundled-pipeline loop shipped broken through a full green suite.

## CB-2 — `E-FLOW-01`: a project registered by one process is active in the next

`tests/e2e/core/config/test_config_db_across_processes_e2e.py`, five subprocesses. `sw init alpha`,
`sw init beta`, `sw use alpha`, `sw projects` — the second registration must not win by being last.

The round trip passed on the first run; the config DB works. The **second** claim did not:
`sw run --json` promises *"NDJSON event stream (machine-readable)"* and emitted twelve schema lines
and four log records around six real events. Two causes, both writing over stdout:

- `db_bootstrap.py:31-33` — three `print()` calls dumping table names on every bootstrap;
- `telemetry_logger.py:160` — `RichHandler()` with no console argument, under a comment reading
  *"Console handler (stderr, WARNING+ only)"*. A bare `RichHandler` writes to **stdout**.

### Proof, per claim

| Claim | Proven by | Tier |
|---|---|---|
| the round trip | `TestTheActiveProjectSurvivesTheProcessBoundary` (2 cases) | e2e |
| FR-2 | `TestTheConfigDbDoesNotSpeakOverTheCommand::test_every_line_of_the_json_event_stream_parses` | e2e |

**The assertion is "every line parses", not `"Base tables" not in stdout`.** Naming the string that
used to be printed passes the moment somebody rewords the debug line while the stream stays
unparseable.

**The logging change is repo-wide**, so the boundary runs the full suite rather than the scoped
tiers: moving records from stdout to stderr is invisible to most tests and fatal to any that read a
warning out of `result.stdout`.

## Done when every mutant is killed

`TECH-054_mutants.json`, run by `mutation.py --corpus`:

| Mutant | FR | Result |
|---|---|---|
| discovery matches nothing | FR-1 | KILLED ×7 |
| `ORDER BY … DESC` becomes `ASC` | FR-1 | KILLED ×1 |
| resumable-status filter inverted | FR-1 | KILLED ×8 |
| project filter inverted | FR-1 | KILLED ×8 |
| resume restarts from step zero | FR-1 | KILLED ×1 scoped, ×14 suite-wide |
| bootstrap prints its schema again | FR-2 | KILLED ×1 |
| log records return to stdout | FR-2 | KILLED ×1 |
| the active project never changes | FR-2 | KILLED ×1 |

**Every FR-2 mutant is killed by exactly one test**, which is what a journey proof looks like and
also its weakness: one skip and the claim is unguarded. Recorded rather than padded — writing a
second test that asserts the same thing twice would hide the fact instead of fixing it. The corpus
is where this stays visible, since `symbol_sha` drift reports `STALE` the moment any of the three
lines moves.

## Out of scope

- **The other seventeen capabilities with no design.** Ratcheted by `TECH-053`, paid down by
  `specweaver-dev` 3.2c on contact. Writing their designs is the thing this ticket exists to avoid.
- **A design document for `D-FLOW-01` or `E-FLOW-01`.** Same reason, one level down: the FRs above
  describe defects that were repaired, not the capabilities' original intent, and nobody now knows
  what that was.
- **Any other stdout writer.** FR-2 is proven through one documented channel (`sw run --json`).
  A repo-wide "nothing prints" rule is a gate, and gates are `TECH-053`'s business.
