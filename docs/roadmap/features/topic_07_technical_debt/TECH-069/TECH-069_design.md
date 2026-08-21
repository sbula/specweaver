# Design: Nothing Read a Design Against the Must-Not-Guess Triggers

- **Feature ID**: TECH-069
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DRAFT
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-069/TECH-069_design.md
- **Origin**: 2026-08-21, from the red/blue review of the must-not-guess trigger rule. Finding
  `R-1.1`: the rule was advisory because no gate compared a design against it.

> **Proportionality.** One check script and a ratchet. It is a ticket because the gate shipped with
> no registry entry, no FR table and no mutants — a quality gate nothing governs is the same defect
> class it exists to catch, and because a corpus has nowhere to live without an ID.

## Problem Statement

`.agents/PRINCIPLES.md` §2 names the decisions an agent may not take alone. Nothing read a design
against that list, so the list was advisory: an agent could settle a spend ceiling, a retention
period or a proven-verdict, write it into a design, and pass every gate in the repository.

This repository's most-repeated defect is a guard that cannot fail. The rule written to stop
guessing was one.

Measured 2026-08-21: **137 designs, none carrying a `Decisions taken with the user` section.**

## Decisions taken with the user

- `T-SPEND`, `T-BOUNDARY`, `T-UNDO`, `T-DATA`, `T-OBLIGATION`, `T-ARCH`, `T-DIVERGE`, `T-PROVEN`,
  `T-ORDER`: not touched. No spend, no security boundary, nothing deleted or migrated, no retained
  or exported data, no new dependency, no module placement question, nothing built other than what
  the FR table states, nothing declared proven, and the roadmap's Debt Sequencing already answers
  what precedes what.
- `T-SCOPE`: fired — the check ratchets over existing designs rather than being diff-scoped, so the
  137 are recorded rather than demanded retroactively.
- `T-DEFAULT`: fired — a design accounts for the list only when it names **every** trigger, not at
  least one, because "at least one" is a guard that barely fails. A `fired` trigger must also carry
  what was settled, which is what makes the section evidence rather than a checklist.
- `T-POSTURE`: fired — a mention the parser cannot read counts as missing, while a design not yet
  designed is exempt rather than counted, and a missing or
  unreadable baseline fails closed. A ratchet nobody can read is not a ratchet.
- `T-NAME`: fired — `TECH-069` minted after both authoritative commands proved it free. The two
  disagreed at `TECH-099`, which is fixture data in `tests/unit/scripts/test_check_roadmap_sync.py`,
  not a ticket.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|---|---|---|---|
| FR-1 | One list, one place | the check | read the trigger IDs from `PRINCIPLES.md` §2's table, and only from table rows | adding or dropping a trigger stays a single-place edit, and prose cannot invent one |
| FR-2 | Every trigger accounted for | the check | require a design's `Decisions taken with the user` section to name every trigger | naming one trigger and stopping does not pass |
| FR-3 | A fired trigger carries its answer | the check | require text recording what was settled after the `fired` marker | the section is evidence, not a checklist |
| FR-4 | Unreadable counts as missing | the check | treat a trigger mentioned without a marker as unaccounted | an unreadable design goes red rather than quiet |
| FR-6 | A stub has nothing to record | the check | exempt a design whose status line reads `STUB` | a freshly minted ticket does not fail the gate for lacking decisions it cannot yet have, and the exemption keys on the status line so it cannot swallow a real design |
| FR-5 | The count may fall, never rise | the check | compare the unaccounted count against a recorded baseline, failing closed when the baseline is missing or unreadable | the backlog cannot grow, and a broken ratchet cannot read as a pass |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|---|---|
| NFR-1 | Gate placement | Runs on the `doc` track, repo-wide, because the trigger list changes rather than the diff. **[proof: meta — rule about which gate the check joins]** |
| NFR-2 | Baseline hygiene | The baseline is version-controlled under `scripts/baselines/` and never written by the suite (`TECH-055` guard) |

## Verifiable Proof

`tests/unit/scripts/test_check_decision_citations.py` — 27 tests, all passing, none skipped.
`docs/roadmap/features/topic_07_technical_debt/TECH-069/TECH-069_mutants.json` — six authored
mutants, one per FR.

## Non-Goals

- Demanding the 137 existing designs be corrected. The ratchet records them; nothing forces the
  backlog down.
- Checking what a decision *was*. The gate checks that a trigger was accounted for and that a fired
  one carries an answer; whether the answer is good is Phase 6's job, not a checker's.
- Enforcing the rule anywhere but designs. Implementation plans and walkthroughs are out of scope.

## Next Step

Delivered and committed (`0f1f0c02`). Awaiting the Phase 6 approval gate, which only the user can run.
