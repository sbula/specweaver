# Design: A Design the FR Gate Cannot Parse Reports "Cannot Run", Not "Failed"

- **Feature ID**: TECH-048
- **Epic**: Topic 07 (Technical Debt)
- **Status**: 🟢 **DELIVERED 2026-08-13.** Approaches 1 and 2; approach 3 deliberately not taken.
- **Origin**: 2026-08-13, from `docs/analysis/test_coverage_audit_2026-08-13.md`. The second of the
  two systemic causes it isolated; the first is `TECH-047`.

## Problem Statement

`check_fr_coverage.py` has three outcomes, and only two of them are honest.

| Outcome | Meaning |
|---|---|
| exit 0 | every FR carried by a plan and cited by a test |
| `BLOCKED` | requirements stated, coverage incomplete |
| **`FAIL  no FR rows parsed`** | **ambiguous** |

The third collapses two different situations into one message:

- the design states **no requirements at all**, so there is nothing to verify against; or
- the design **does state requirements and the parser cannot read them**.

Measured 2026-08-13 across 47 delivered capabilities, five land here — and they split evenly across
that ambiguity:

| Capability | Which |
|---|---|
| `C-EXEC-01` | no requirements of any kind |
| `C-VAL-03` | no requirements of any kind |
| `E-UI-02` | no requirements — design written after delivery as a record (`TECH-044`), expected |
| `C-SENS-02` | **`FR-` ids present, table format unreadable to the parser** |
| `D-SENS-03` | **`FR-` ids present, table format unreadable to the parser** |

**The last two are the defect.** A capability whose design states requirements the checker silently
cannot parse is, from the outside, indistinguishable from one that has nothing to check. It is the
same disease as a story-scoped check nobody invokes — the gate produces no signal and the absence
of signal reads as health.

## Why this is small but worth a ticket

Two instances is not much. The reason to fix it is that **the failure mode scales with adoption**:
every new design format variation silently removes a capability from the gate's reach, and nothing
reports that the reach shrank. `TECH-047` is about to make this gate sweep everything — a sweep
whose blind spots are invisible is worse than one that admits them.

## Candidate Approaches — 1 and 2 taken

1. **Split the outcome.** `no requirements stated` and `requirements present but unparseable`
   become different exits with different messages. The second should be a hard failure: the parser
   is wrong, or the design is malformed, and either way somebody must look.
2. **Make the parser accept what designs actually use.** Read `C-SENS-02` and `D-SENS-03` first —
   the fix may be as small as one more table shape. Do not generalise from two samples without
   checking the other 45.
3. **Require an FR table in a capability design, enforced.** The `specweaver-design` skill already
   mandates Functional Requirements in its phase-3 Section A; nothing checks that it happened.
   Note this must NOT apply to `TECH` tickets — their stub has no requirements table by design, and
   26 delivered tickets legitimately have none. Conflating the two is the error the audit itself
   made and corrected.

(1) is the load-bearing one. (2) without (1) fixes two instances and leaves the blindness.

## Non-Goals — all held

- Adding FR tables to delivered capability designs. That is specification archaeology on finished
  work and needs its own decision; `finished-stories-immutable` applies.
- `TECH` tickets. They have no FR table by design and must stay that way.
- The sweep itself — `TECH-047`.
- The 40 capabilities the gate CAN run on and fails — verification work, `TECH-017`'s matrix.

## Delivery, 2026-08-13

### The deciding question: the parser was wrong, not the designs

`specweaver-design` phase-3 Section A requires each FR to be **numbered, unambiguous, testable and
structured** — and says **nothing about a table**. `C-SENS-02` and `D-SENS-03` declare theirs as
bullets (`- **FR-1:** ...`), which is conforming. The table-only rule was invented by the parser.

So this was a checker fix. The table-only rule was not arbitrary, though: it stopped prose like
`- **FRs**: [FR-1, FR-2]` in a sub-feature breakdown from inventing ledger entries a story can
never satisfy. That protection is preserved by requiring the id to be the **subject** of the line —
directly after the marker, followed by a colon — rather than merely present on it.

### Approach 1, the load-bearing half: the outcome is split

`no FR rows parsed` collapsed two situations calling for opposite responses. They are now separate
messages: **states no Functional Requirements** (the design needs work) and **mentions FR-N but
cannot read them as declarations** (the parser or the design's shape needs work, and *the gate's
reach has shrunk silently*). Both still block — reporting zero FRs as full coverage would be a
vacuous pass either way.

### A false positive found by measuring instead of trusting

Running the new message across all 61 capability designs, its only two hits were **both wrong**:
`B-EXEC-04` cites `C-EXEC-02 FR-11` and `C-FLOW-12` cites ``INT-US-21's `FR-9(a)` `` — neighbours'
requirements, correctly referenced. Telling a reader to go fix a parser bug that is not there is
exactly the noise that gets a checker ignored. Foreign references are now excluded, and a design
citing a neighbour reads as the stub it is.

### Result

| | before | after |
|---|---|---|
| gate cannot run | 5 | **0 unreadable**, 14 "no requirements" (all undelivered stubs) |
| `BLOCKED` | 43 | 45 — `C-SENS-02` and `D-SENS-03` moved here, which is an actionable verdict |

### Approach 3 deliberately not taken

Requiring an FR table in a capability design would need to tell a **stub** from a **delivered**
capability: all 14 remaining "no requirements" are stubs for unbuilt work, which legitimately have
none. That distinction is `TECH-047`'s — it is the ticket about sweeping *delivered* work — and
building it here would duplicate the harder half of it.
