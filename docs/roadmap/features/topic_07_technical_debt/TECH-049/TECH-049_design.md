# Design: Nothing Verifies a Test Was Red Before the Code It Covers

- **Feature ID**: TECH-049
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-15, from the `ADR-003` skill-coverage audit run while retiring
  `INT-US-04-SF09`. The audit asked whether the "integration and e2e tests are written before the
  code" rule reached the skills. It did — in five of seven. Nothing checks it.

## Problem Statement

`ADR-003` made test **sequencing** load-bearing. Integration no longer has its own story, so the
seam test is written by the capability that creates the seam, at the boundary where *"the interface
first exists and the behaviour does not yet"*. The ADR states plainly why:

> A test written after the code it covers has never failed for the right reason.

The rule is well encoded as **instruction**. It is encoded **nowhere as a check**.

| Layer | Encodes the rule? | Enforces it? |
|---|---|---|
| `specweaver-design` (`phase-3-detail.md` A.1a–A.1d) | ✅ seams are FRs; bindings table; HITL gate | — |
| `specweaver-implementation-plan` (`SKILL.md`, `phase-1-preparation.md`) | ✅ tier table; write-the-seam-test-between-steps; *"record the red and its reason"* | ❌ |
| `specweaver-dev` (`SKILL.md` 3.1 Red) | ✅ strict red-before-implementation mandate | ❌ |
| `specweaver-pre-commit` (`phase-2`, `phase-4`) | ✅ tier gap matrix, tier profile | runs tiers, cannot see ordering |
| `scripts/` | — | **no script reads a plan or walkthrough for a recorded red** |

`ADR-003` admits the gap in its own §*Test sequencing*: the recorded red is
*"a partial answer to `TECH-025` NFR-3 … which nothing currently checks."*

`TECH-025` NFR-3 states the same requirement from the citation side — *"every `Proves:` tag names a
test that would fail if that FR's behaviour regressed"* — and is likewise unenforced. **Both
statements of the rule are discipline-only, and they are the two that matter most**, because every
gate downstream trusts them: `check_fr_coverage.py` proves a test *exists* and is *cited*, never
that it can fail.

### This has already produced a false green in this repo

`TECH-017` wrote a containment test that passed on first run and proved nothing — the function it
covered returned `{}` for every caller, so the assertion could not fail. It was a **mutant**, run by
hand, that exposed it; chasing the mutant found a key mismatch that had kept skeleton context out of
every generation and review prompt since the feature shipped. A green test suite concealed a live
production defect for months, and no gate was capable of noticing.

## Candidate Approaches (not yet designed)

1. **Parse the plan/walkthrough for a recorded red.** Require a structured `Red:` field per commit
   boundary that introduces a test, naming the test and the reason it failed. Cheap; checks that
   the claim was *written*, not that it is *true*. Vulnerable to the exact document-state lie
   `check_story_preconditions.py` exists to catch.
2. **Require a killed mutant per new test citation.** Extend `scripts/_mutate.py` (already used
   this way by hand, already invoked from the implementation-plan skill's Done-when contract) into
   a gate: a `Proves:` tag is valid only if neutralising the line it covers turns that test red.
   Strongest evidence, directly discharges `TECH-025` NFR-3, and costs real runtime — the cost
   profile needs measuring before it can be scoped.
3. **Check commit ordering in git.** A test file's first commit must not post-date the
   implementation it cites. Fully mechanical and free, but blind to the within-commit case, which
   is the normal one here — the project commits red and green together at a boundary.

Not mutually exclusive: 3 is a cheap always-on floor, 2 is the real proof, 1 is the audit trail.

## Non-Goals (proposed, pending design)

- Enforcing red-first for **unit** tests beyond what `specweaver-dev` 3.1 already mandates. The
  measured failure is at the seam and journey tiers, which `ADR-003` moved and no separate story
  now double-checks.
- Retrofitting evidence onto delivered stories. `finished-stories-immutable` applies; this gate
  judges what is written next, exactly as `ADR-003` did.
- Replacing `check_fr_coverage.py` or `check_proof_tier.py`. This is the missing third question
  (*can the cited test fail?*) alongside their two (*does it exist? is it the right tier?*).

## The decision this ticket exists to force

**What counts as machine-checkable evidence that a test was red first** — and what runtime the
project will pay for it. Approach 2 is the only one that proves the property rather than recording
a claim about it, and it is the only one whose cost is unknown. That is a scope decision, not an
implementation detail, which is why this is a ticket rather than a fix.

**Ship the guardrail with the fix**: whichever approach lands must also be applied to the skills
that currently only *say* the rule, so the instruction and the gate cannot drift apart.

## Next Step

Run `specweaver-design TECH-049`. Measure approach 2's runtime over a representative story before
the Phase 4 HITL gate — the cost is the decision.
