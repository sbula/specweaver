# Design: The Two Foundations Nobody Wrote Down

- **Feature ID**: TECH-054
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DRAFT
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

## Functional Requirements

None, deliberately — `ADR-003`: *"a journey artifact declares no FRs of its own, builds nothing, and
writes no unit tests."* Its deliverable is e2e proof. If writing one of these turns out to need a
unit test, that is the diagnostic that the capability underneath shipped incomplete, and the finding
belongs to that capability.

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
| **CB-1** | `D-FLOW-01` — a pipeline runs and its state survives a resume |
| **CB-2** | `E-FLOW-01` — a project registered in one process is active in the next |

Each is done when its mutant kills it, not when it goes green: both capabilities work today, so a
passing test proves only that it was written.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Single feature | — | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design DRAFT.
**Next step**: CB-1. The other seventeen are ratcheted by `TECH-053` and paid down by
`specweaver-dev` 3.2c on contact; that is the decision, not an omission.
