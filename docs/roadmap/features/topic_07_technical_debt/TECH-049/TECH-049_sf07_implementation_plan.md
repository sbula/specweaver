# Implementation Plan: Mutation Campaign Corpus and Session Gate [SF-07: Adoption]

- **Feature ID**: TECH-049
- **Sub-Feature**: SF-07 — Adoption
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-07
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf07_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-14.** Depends on: SF-06 (committed).

> **Proportionality.** Documentation and skill edits. One commit boundary. The rigour that applies
> here is `check_skill_sync` and `check_skill_references`, not mutants — there is no behaviour.

## Scope

Make the delivered mechanism usable: teach the skills it exists, describe the morning routine, and
put the commands where someone will find them.

## Why this is a sub-feature and not a footnote

Measured by grep before starting: **zero** mentions of `mutation.py`, `_mutants.json` or `--corpus`
in any skill. `specweaver-dev` 3.2b still teaches only the one-shot `_mutate.py`. So today the gate
blocks work and nothing anywhere says how to clear it — and a gate nobody can clear is a gate that
gets switched off, which is the failure this whole ticket was written to prevent.

## Deliverables

| # | Where | What |
|---|---|---|
| 1 | `specweaver-dev` 3.2b | The corpus alongside the one-shot mutant: when a claim is worth a *campaign* rather than a probe |
| 2 | `specweaver-pre-commit` phase 5 | Where the corpus sits relative to the commit gates — namely, **not in them** (`NFR-6`) |
| 3 | `docs/dev_guides/writing_mutation_campaigns.md` | The morning routine, the four dispositions, and what each means for the census |
| 4 | `CLAUDE.md` | The four commands, beside the existing test and quality commands |

Both skill trees (`.claude/` and `.agents/`) stay byte-identical — `check_skill_sync` enforces it.

## The morning routine, as it will be written

```
mutation.py --gate          # CLEAR, or BLOCKED with the unconfirmed findings named
```

For each finding, read its `breaks` field — it says what bug was planted — then decide:

| Disposition | Means | Counts toward the census |
|---|---|---|
| `real-gap` | the requirement genuinely is not protected; you fixed it or wrote the test | No |
| `equivalent` | the mutant changes no observable behaviour, so surviving proves nothing | **Yes** |
| `will-fix` | real, and you are continuing anyway | **Yes** |
| `stale-refreshed` | the code moved; you re-read the claim and re-pinned it | No |

A `STALE` finding means the code a claim rested on moved: re-read the claim, then
`_corpus.py --refresh`. **Recurrence counts are the pressure** — they show which `will-fix` has been
re-confirmed for a fortnight, which is why no re-run is demanded to prove a fix.

## Commit boundary — CB-1

**Delivers:** the four documents above.

**Tests:** `check_skill_sync` (both trees identical) and `check_skill_references` (every path named
resolves) — both already in `quality.py doc`, both blocking. Plus a documentation test asserting
the guide's commands are the ones `mutation.py --help` actually accepts, because a guide naming a
flag that does not exist is worse than no guide.

**Done when** the documented commands are the real ones: the test kills a mutant on a renamed flag.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | The guide drifts from the CLI as flags change | The doc test binds them: rename a flag and it fails |
| R-2 | Skill edits land in one tree only | `check_skill_sync`, already blocking in `quality.py doc` |
| R-3 | The routine is written and never followed | Out of scope for a plan to fix. The gate blocking is the forcing function |

## Delivered

One boundary. Full suite 7126 passed, 0 failed. `check_fr_coverage TECH-049` exits 0.

**Finding: this sub-feature's gate caught a defect SF-06 had introduced.** `prune_orphaned_sandboxes`
matched on the prefix alone, so it deleted sandboxes concurrent xdist workers were mid-run in —
orphan cleanup broke parallel runs that had been working. Surfaced by the integration tier under
`-n auto`. Age is the discriminator now: a live session is minutes old, a leak outlives the night.

## Out of scope

Any change to the mechanism. If adoption reveals a defect, it is a finding against the sub-feature
that owns it, not a reason to edit code here.
