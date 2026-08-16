# Design: A `✅` Nothing Can Verify

- **Feature ID**: TECH-053
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DRAFT
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-053/TECH-053_design.md
- **Origin**: 2026-08-16. An agent flipped two roadmap add-on groups to `🟢` from their children's
  checkboxes, called it *"computed from the children rather than eyeballed"*, and was asked whether
  there was any evidence behind it. There was not.

> **Proportionality.** One new check and a ticket's worth of findings. What earns the space is the
> measurement: the number is far larger than the incident that exposed it.

## Feature Overview

`TECH-053` makes two unverifiable claims visible. First, a roadmap **add-on group flag** that
disagrees with its own children — nothing compares them, so a group can say *"zero requirements
checked"* while every capability under it is `✅`, or the reverse. Second, a capability marked `✅`
that **`check_fr_sweep.py` structurally cannot see**: one with no design document at all, or a
design declaring no FRs. Both are `✅` claims with nothing behind them, and the existing ratchet
counts uncited FRs — so a capability with *no FRs to cite* scores zero and looks perfect.

## Research Findings

### What triggered it

Six add-on group flags disagreed with their children (`577744b3` corrected them by arithmetic).
Two of the six became `🟢`, and the capabilities under them turn out to be:

| Capability | Marked | Ledger |
|---|---|---|
| `B-VAL-01` AST Drift Detection | ✅ | 6 FRs declared, **0 cited by any test**, 5 carried by no plan |
| `D-VAL-04` Adaptive Assurance Standards | ✅ | 4 FRs, **0 cited**, 0 planned |
| `C-VAL-03` Dynamic Risk Rulesets | ✅ | design declares **no FRs at all** |
| `D-VAL-02` Custom Rule Paths | ✅ | **no design document exists** |

So *Code-to-Spec Drift Checking* `🟢` rests on one capability with no cited proof, and *Dynamic Risk
Controls* `🟢` on three, one with no design and one with no requirements.

### The population, measured 2026-08-16

Every capability marked `✅` in `capability_matrix.md`, judged by its own ledger:

| | |
|---|---|
| capabilities marked `✅` | **62** |
| FRs declared but uncited or unplanned | **39** |
| **no design document at all** | **19** |
| **design declares no FRs** | **3** |
| **clean** | **1** |

The single clean one is `A-VAL-01`, fixed by `TECH-051` the same day. The `2026-08-13` closure
contract measured the adjacent population (103 capabilities *with* a design: 8 clean, 46 blocked,
49 unrunnable); this is the same rot counted from the matrix side.

### Why the existing ratchet cannot see 22 of them

`check_fr_sweep.py` counts **uncited FRs across delivered designs**. A capability with no design
contributes no design; one with no FRs contributes no FRs. Both score **zero uncited** and are
indistinguishable from perfect. That is not a flaw in the sweep — it counts what it says it counts —
but it means the 19 + 3 are invisible to every gate in the repo.

### What is deliberately NOT duplicated

The 39 with uncited FRs are **already** ratcheted by `check_fr_sweep.py` at 234. Adding a second
rule for one number would mean two baselines to freeze and two places to argue about. This check
covers only what that sweep is structurally blind to.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A group flag agrees with its children | check | SHALL fail when an add-on group's status flag disagrees with the checkbox state of the capabilities listed under it — `🟢` iff all are `✅`, `🔴` iff none are, `🟡` otherwise | The arithmetic that six groups got wrong stops being something a person has to notice |
| FR-2 | A delivered capability has something to verify | check | SHALL report every capability marked `✅` in the matrix that has **no design document** or whose design **declares no FRs**, ratcheted against a frozen baseline so the count may fall and never rise | The 22 claims no other gate can see become countable, and the 23rd is blocked |
| FR-3 | The finding names the remedy, not just the count | check | Each reported capability SHALL be named with which of the two causes applies | *"write the design"* and *"declare the FRs"* are different jobs, and a bare number is neither |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Cheap enough for the `doc` gate | Reads the matrix and the features tree; no subprocess per capability. The 62-capability census above took a parallel subprocess fan-out and is far too slow to repeat on every run |
| NFR-2 | A ratchet, not a wall | 22 findings exist today and cannot be fixed in this ticket — writing 19 design documents is not a debt ticket, it is a programme. The baseline freezes today's count; growth blocks. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-3 | FR-1 is zero-tolerance | All six known disagreements were corrected in `577744b3`, so there is no backlog to ratchet and a baseline would only invite one |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Two rules, one check | They answer one question — *"is this `✅` backed by anything?"* — from the group side and the capability side. Splitting them would make the group rule look like formatting rather than evidence | No |
| AD-2 | Do not re-count the 39 uncited-FR capabilities | `check_fr_sweep.py` ratchets them already. Two gates for one number is two baselines and one argument | No |
| AD-3 | Report, do not fix, the 22 | Writing 19 missing design documents is a programme, not a boundary. The ticket's job is to make them countable and to stop the 23rd | No |

## Sub-Feature Breakdown

**Single feature — no decomposition.** 3 FRs, one new script, one registration.

## Execution Order

One commit boundary. The check is written against synthetic fixtures (red: it does not exist), the
baseline is frozen at today's 22, and FR-1 passes on arrival because `577744b3` already corrected
the six groups — with the check's own tests proving it fires on a synthetic disagreement.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Single feature | — | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design DRAFT.
**Next step**: implement; the four capabilities named above stay open as this ticket's findings.
