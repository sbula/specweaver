# Design: A Design the FR Gate Cannot Parse Reports "Cannot Run", Not "Failed"

- **Feature ID**: TECH-048
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
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

## Candidate Approaches (not yet designed)

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

## Non-Goals (proposed, pending design)

- Adding FR tables to delivered capability designs. That is specification archaeology on finished
  work and needs its own decision; `finished-stories-immutable` applies.
- `TECH` tickets. They have no FR table by design and must stay that way.
- The sweep itself — `TECH-047`.
- The 40 capabilities the gate CAN run on and fails — verification work, `TECH-017`'s matrix.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation. Start by reading
`C-SENS-02` and `D-SENS-03`'s FR tables and establishing whether the parser or the design is wrong;
the answer decides whether this is a checker fix or a convention fix.
