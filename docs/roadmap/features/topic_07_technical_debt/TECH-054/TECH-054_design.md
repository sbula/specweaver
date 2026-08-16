# Design: The Two Foundations Nobody Wrote Down

- **Feature ID**: TECH-054
- **Epic**: Topic 07 (Technical Debt)
- **Status**: APPROVED (2026-08-16)
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-054/TECH-054_design.md
- **Origin**: 2026-08-16, from `TECH-053`. Nineteen capabilities are marked `✅` with no design
  document. Seventeen of them stay ratcheted; these two do not, because everything runs on them.

> **Proportionality.** Two e2e journeys. The restraint is the design: the obvious response to
> nineteen missing designs is nineteen designs, and that is the wrong answer.

## Feature Overview

`TECH-054` gives the two load-bearing Step-era capabilities one falsifiable claim each.
`D-FLOW-01` (Pipeline Runner) and `E-FLOW-01` (Config DB) sit underneath every command in the
product, and their entire written record is a topic-entry sentence — `D-FLOW-01`'s reads, in full,
*"SQLite Pipeline Runner & State Persistence."* It does not touch the other seventeen, which the
`TECH-053` ratchet holds at 22, and it does **not** write either capability a design document.

## Why a journey proof and not a design

There is nothing to backfill *from*. No plan, no FR table, no recorded intent — only code that has
worked for months. A design written now would be read off the implementation, and **a requirement
derived from the code it describes can never fail**: it is a paraphrase wearing the costume of a
claim, and the ledger would then report it as proven while proving nothing. That is the failure
`TECH-051` and `TECH-053` each found in their own work, twice, caught only by mutation.

A journey proof escapes it. `ADR-003` already defines the shape: e2e only, declares no FRs,
implements nothing. It states what must remain true from outside the code, so it can be wrong, and
it can be checked by someone who never reads the implementation.

**What each capability gets is therefore one sentence that can fail**, not a reconstructed spec:

| Capability | The claim |
|---|---|
| `D-FLOW-01` Pipeline Runner | a pipeline runs, and its state survives into a resume |
| `E-FLOW-01` Config DB | a project registered by one process is the active project in the next |

## Why these two and not the other seventeen

Ordering by blast radius rather than by tidiness. Every `sw run`, `sw resume` and `sw implement`
goes through the runner; every command that resolves an active project goes through the config DB —
including `sw usage`, whose two defects this session already fixed. `E-SENS-02` (Agentic Research
Tools) has the same empty record and nothing depends on it in the same way.

Seventeen stay ratcheted **and the ticket says so**, so the question is not reopened in three
months as though nobody had considered it.

## What the first journey found, before it was written down

Both defects below were found by **probing the journey by hand**, in under ten minutes, on a
capability that has been `✅` for months. They are the argument for the ticket, so they are recorded
before the requirements they caused.

`sw run` accepts *"Pipeline name or YAML path"* — its own `--help` says so, twice, and the runner
loads either. `sw resume` with no argument then does this
(`src/specweaver/core/flow/interfaces/cli.py:471`):

```python
for pipeline_name in list_bundled_pipelines():
    candidate = store.get_latest_run(name, pipeline_name)
```

1. **A run of any pipeline that is not one of the 14 bundled ones can never be auto-resumed.** It
   is absent from the loop, so `sw resume` reports *"No resumable runs found for the active
   project"* while the row sits in `flow_pipeline_runs` with `status='failed'`. The state persisted
   perfectly; nothing could find it. `sw resume <run-id>` still works — `load_run` has no such
   filter — so the failure is discovery, and it is silent, which is worse than an error.
2. **"Latest" is not latest.** The loop returns the first *bundled-list* entry that has a resumable
   run, so a month-old `new_feature` failure wins over a parked `validate_only` from a minute ago.
   The docstring one line above promises *"the newest resumable one."*

This is what a journey proof is for. Neither defect is visible from inside a unit test of the
runner, both are on the first path a user takes, and the capability's own record is one sentence.

## Functional Requirements

`ADR-003` says a journey artifact *"declares no FRs of its own, builds nothing, and writes no unit
tests"* — and this design predicted the exception: *if writing one turns out to need more, that is
the diagnostic that the capability underneath shipped incomplete.* It did, so `TECH-054` owns the
fix. `D-FLOW-01` is `✅` and `finished-stories-immutable` puts it out of reach; a ticket is where
the repair belongs.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Auto-detect finds the newest resumable run for the active project, whatever pipeline produced it | A developer whose run failed | runs `sw resume` with no arguments | the run that failed last is resumed — including one started from a YAML path, which today is invisible |

One requirement, because both defects are the same three lines and the same missing query: the
store can answer *"latest resumable run for this project"* directly, and `_resolve_resumable_run`
should ask it rather than reconstructing the answer from a list of names that has nothing to do
with what ran.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Each journey must be able to fail | Proven by mutation, not by passing: neutralise the persistence each claim rests on and the journey must die. A journey over working machinery that no mutant can kill is describing the code. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-2 | No LLM, no network | Both journeys are about persistence and process boundaries. A pipeline that needs a model to prove its state survives is testing the wrong thing |
| NFR-3 | Nothing is written to the user's real database | `SPECWEAVER_DATA_DIR` into `tmp_path`, the way `tests/e2e/conftest.py::_isolate_env` already does for the tier |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Journey proofs, not designs | A spec reverse-engineered from its own implementation cannot be falsified. This is the whole reason the ticket exists rather than a backfill programme | No |
| AD-2 | Two capabilities, not nineteen | Ordered by what depends on them. Completeness here would mean seventeen more unfalsifiable claims | No |
| AD-3 | The remaining seventeen are addressed by a **rule**, not this ticket | `specweaver-dev` 3.2c: a boundary that touches a capability with no FRs gives it FRs, mutant-checked. The number shrinks as work happens rather than as a project | No |

## Sub-Feature Breakdown

**Single feature — no decomposition.** Two journeys, no FRs, one module of test code each.

## Execution Order

| Boundary | Delivers |
|---|---|
| **CB-1** | `D-FLOW-01` — the journey, plus FR-1: the resume-discovery defect it exposed |
| **CB-2** | `E-FLOW-01` — a project registered in one process is active in the next |

CB-1 is the ordinary case for once: the journey is written first and **fails for the right reason**,
because the behaviour it claims does not exist. CB-2 has no such luck — the config DB works — so it
is done when its mutant kills it, not when it goes green.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Single feature | — | ✅ | ✅ | 🔄 | ⬜ | ⬜ |

## Session Handoff

**Current status**: CB-1 committed. The `D-FLOW-01` journey is green and FR-1 is proven — five
mutants, all killed, pinned in `TECH-054_mutants.json`.

**What CB-1 settled about the capability.** Resume splits into two halves and only one was covered.
*Persistence* is well protected: neutralising it (`run.current_step = 0` before the loop) is killed
by **14 tests across three tiers**. *Discovery* had nothing — the bundled-pipeline loop shipped
broken through a full green suite, and no test in the repo could see it. That asymmetry, not the
defect, is the reusable finding: coverage clustered on the mechanism and left the path a user takes
to reach it unguarded.

**Next step**: CB-2 — `E-FLOW-01`, plus the three `print()` calls in
`core/config/bootstrap/db_bootstrap.py:31-33` that dump the schema to **stdout** on every bootstrap.
The other seventeen are ratcheted by `TECH-053` and paid down by `specweaver-dev` 3.2c on contact;
that is the decision, not an omission.
