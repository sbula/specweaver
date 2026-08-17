# Implementation Plan: TECH-060 — Integration Migration Machinery

- **Feature ID**: TECH-060
- **Design**: [TECH-060_design.md](TECH-060_design.md)
- **Authority**: `ADR-004`

**FRs owned: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6.** One plan — the deliverables are independent
enough to land in sequence and too small to decompose. FR-7 was deleted from the design rather than
delivered; see the note there.

## Commit boundaries

| CB | FRs | Delivers | Landed |
|---|---|---|---|
| CB-1 | FR-1 | The `-MIG` identifier accepted wherever an `INT-US` id is parsed | `9ee8e6b9` |
| CB-2 | FR-2, FR-3 | The migration registry, five minted contract ids, three honest checkboxes | `3c068af7` |
| CB-3 | FR-4 | No green over closed features without a delivered contract | `66d4b8df` |
| CB-4 | FR-5 | A strict xfail names an unbuilt blocker | `7cdfdd94` |
| CB-5 | FR-6 | The method in four skills, both trees | `5ec8f4e9` |

CB-2 is one boundary rather than two because FR-3's consequence is immediate: minting a contract line
under a `🟢` group gives it an open child, so `group_flag_findings` fires in the same breath. Splitting
them would mean committing a registry the `doc` gate rejects.

## What each boundary proved

**CB-1.** Probing every candidate site changed the count from four to two and then to three, and
found a defect reading could not: `_RETIRED_ID` **matches** `INT-US-06-MIG` and truncates it to
`INT-US-06`, attributing a migration line's retirement note to the base contract. A third site —
`check_roadmap_placement.py`'s `STORY_ID` — surfaced only when CB-2 minted `INT-US-21-SUB` and
R-PLACE reported a legitimate entry as a design's internal decomposition. The lesson is narrow and
worth keeping: **I probed the sites I had already listed instead of searching for sites**, and the
one I had not listed is the one that broke.

**CB-2.** Generating the roster rather than counting it corrected 26 to 27 — the design's own table
counted four un-IDed groups and named the fifth in prose beside the count.

**CB-3.** Measuring before implementing changed the rule from ratcheted to zero-tolerance. The design
assumed it would fire on all 27 units; it fires on none, because those units are `🟡` or their
contracts are `[ ]`. A ratchet would have frozen zero.

**CB-4.** `strict=True` already makes the suite complain when a blocker ships, so the gate exists for
the *interpretation*: an unexpected pass reads as "the test is broken" and the tempting fix is
deleting the assertion. The matrix knows the real answer.

**CB-5.** Pinning skill prose is brittle, and the first draft proved it — an assertion on
`"must** be named"` failed because the skill wraps that clause across two lines. Every pinned clause
is now unbreakable by wrapping. A rule that cries wolf on formatting is a rule someone deletes.

## Verification

| FR | Proof | Tier |
|---|---|---|
| FR-1 | `test_tests_runner.py`, `test_check_roadmap_placement.py`, `test_check_retirement_targets.py` | unit |
| FR-2 | the live-registry assertions in `test_check_delivered_claims.py` | unit |
| FR-3 | same, plus `check_proof_tier` and `check_delivered_claims` agreeing on the live tree | unit |
| FR-4 | `test_check_delivered_claims.py::TestUnprovenGreenFindings`, 8 cases | unit |
| FR-5 | `test_check_xfail_blockers.py`, 12 cases | unit |
| FR-6 | `test_story_contract_rule.py`, 12 cases across both skill trees | unit |

Both gates were **probed on the live tree**, not only against fixtures: a green group stripped of its
contract turns `doc` red, and a planted strict xfail naming shipped `C-FLOW-05` does the same. Each
was then restored and the gate returned to green. A passing gate and an inert gate look identical
otherwise — which `R-OWNER` and the morning mutation gate both demonstrated by shipping inert.

## Out of scope

The 27 inventories themselves, the 17 already-proven contracts, and
`check_retirement_targets.py`'s missing second question. All three are recorded as non-goals in the
design with the reasoning.
