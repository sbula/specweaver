# Design: Nothing Read a Design Against the Must-Not-Guess Triggers

- **Feature ID**: TECH-069
- **Epic**: Topic 07 (Technical Debt)
- **Status**: ⚰️ RETIRED 2026-08-23 — see the banner above. Never approved; Phase 6 never ran.
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-069/TECH-069_design.md
- **Origin**: 2026-08-21, from the red/blue review of the must-not-guess trigger rule. Finding
  `R-1.1`: the rule was advisory because no gate compared a design against it.

> **⚰️ RETIRED 2026-08-23 by the user.** Ruled **oversold** under the benefit test: the check
> looked for keywords, never for truth. One bullet naming all 13 triggers `not touched` passes it,
> and flipping `fired — <answer>` to `not touched` passes it while deleting the answer. It never
> read the rest of the design, so it could not contradict a claim its own section made. The deeper
> fault is that guaranteeing the section EXISTS converts the safe failure — an agent finds nothing
> and asks the user — into the unsafe one, where it finds a possibly-rotten answer and builds on
> it; and `what the user agreed` is testimony, so a stale entry can never be recomputed and caught.
> `PRINCIPLES.md` §5 already forbade the second copy. `check_decision_citations.py`, its baseline,
> its 27 tests and its 6 mutants are deleted. The 13 triggers stay in §2 — they work as the agent's
> own detector. A settled decision moves to `` `[agreed <date>]` `` beside the fact it governs; that
> half lands in the commit after this one, so between the two the section is asked for and unread. The FR/NFR tables below were removed with the code so the descope is visible; this
> document remains as the record of what was built and why it was wrong.

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

*Removed 2026-08-23 with the code they described. The design is a record, not a live claim.*

## Non-Functional Requirements

*Removed 2026-08-23 with the code they described.*

## Verifiable Proof

*Withdrawn. The tests and mutants that carried it are deleted.*

## Non-Goals

- Demanding the 137 existing designs be corrected. The ratchet records them; nothing forces the
  backlog down.
- Checking what a decision *was*. The gate checks that a trigger was accounted for and that a fired
  one carries an answer; whether the answer is good is Phase 6's job, not a checker's.
- Enforcing the rule anywhere but designs. Implementation plans and walkthroughs are out of scope.

## Next Step

None. Retired 2026-08-23. The ID is dead and must not be reused.
