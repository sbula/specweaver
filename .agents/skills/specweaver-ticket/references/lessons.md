# Why the rules exist

The incidents behind the rules in `SKILL.md`. Each rule stays in the skill; this file keeps the story.

## A topic doc is not the TECH registry (2026-07-25, real)

An agent grepped only `docs/roadmap/topics/topic_07_technical_debt.md`, saw `TECH-001`..`TECH-008`,
and minted `TECH-009` and `TECH-010`. **Both were already taken** — `TECH-010` had a full design
doc. The topic doc listed only a *subset*; five tickets existed solely as design-doc directories.
The true maximum was `TECH-013`. Three tickets' titles had also drifted from their registry names
as of that date.

## Another skill's prose is not a green light (2026-07-30, real)

`specweaver-pre-commit` Phase 2 told the agent to "raise a story to make it honest" for a
vacuous-test finding. Read as a standing invocation of this skill, that ran Phases 1-5 to
completion — registry entry, design-doc stub, cross-references — inside an unrelated pre-commit
task, with no point where the human was asked whether a new ticket should exist at all.

## A ticket is a last resort

Six tickets were filed on 2026-08-13 in a single day, several as the "outcome" of resolving an
earlier one. The backlog grew; the verification did not.

## Re-measure an audit ticket before planning it

`TECH-018` was filed 2026-07-26 against evidence that `INT-US-21 SF-03` invalidated **two days
later**, by shipping the 24-test CLI journey that was the ticket's own second candidate approach;
re-measuring closed it in one session instead of the "unknown size" it feared, and the same pass
corrected three of `TECH-017`'s findings.

## The `INT-US` family is retired

Measured 2026-08-13: 63 pre-allocated `Sub-Story Integration (Pending Design)` entries existed and
**not one had a design document or a feature directory**. Measured again 2026-08-19, after a full
migration: **31 of 36 open contract rows named another ticket as their blocker** — the same work
written twice.

## A capability is minted as a topic entry only

Measured 2026-08-16 across 153 capabilities: **67 of the 82 unbuilt ones have no feature directory
at all**, while **54 of the 62 delivered ones do** — the design document appears when the work is
picked up. Of the 15 unbuilt exceptions, twelve are active routing-queue candidates and three were
minted the same day by an agent following Phase 3 as if it applied to capabilities.

## Closing is a claim about the implementation

Measured 2026-08-13: **46 of 103 capabilities fail that bar while marked delivered.**
