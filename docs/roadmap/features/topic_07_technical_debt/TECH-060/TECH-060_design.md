# Design: Integration Migration to (Sub)Story Path Inventories

- **Feature ID**: TECH-060
- **Epic**: Topic 07 (Technical Debt)
- **Status**: APPROVED <!-- decisions settled by user interview 2026-08-17 (grill-me), 44 questions -->
- **Origin**: `ADR-004`, which defines the target structure but builds none of the machinery

## Problem Statement

`ADR-004` decided that a (sub)story holding closed features owns an integration story for them, that
the `INT-US` entry **is** that story's contract, and that its spine is a **path inventory** plus the
cross-feature (N)FRs the inventory generates. None of that exists yet. This ticket builds it.

**Measured 2026-08-17 by generating the roster rather than counting by hand — which corrected the
total from 26 to 27.** 27 (sub)stories hold at least one closed capability and cannot prove its
integration:

| Set | Count | State |
|---|---|---|
| Open base contracts | 14 | US-6, 7, 8, 10, 11, 12, 15, 18, 19, 20, 22, 23, 26, 27 — every contract document a ten-line stub reading `[Pending definition...]` / `Verifiable Proof: [Pending]` |
| Add-on groups with an identifier | 5 | `INT-US-01-SF02`, `-01-SF03`, `-03-SF01`, `-04-SF05`, `-09-SF01` |
| Add-on groups with no identifier | 5 | US-10 drift checking, US-11 and US-19 infinite scale, US-15 compliance, US-25 dynamic risk controls |
| Marked `✅`, citing no test file | 3 | `INT-US-05-SF03`, `-05-SF04`, `-21-SUB` — carried by `check_proof_tier.py` as accepted debt |

The fifth un-IDed group is `INT-US-25-SF01`, which `ADR-003` closed empty and `ADR-004` reverses. An
earlier draft of this table named it in prose beside the count instead of inside it, which is how 27
read as 26. Every figure below is now generated, not transcribed.

**Nothing enforces the rule either.** `check_delivered_claims.py` compares a story's flag with its
children's checkboxes and never asks whether the closed children have integration evidence. And
`ADR-004` clause 4 requires a test to be written the moment its interface is defined, marked
`xfail(strict=True)` — with no gate, those markers become permanent exemptions, which is how every
suppression list in this repo decayed.

## Decision

Build the machinery and the registry, not the inventories. Four deliverables.

### 1. The method

Every path in a (sub)story goes to exactly one of three homes:

| Path | Home | Mechanism |
|---|---|---|
| One feature can walk it, runnable today | the feature | backfill on contact (`specweaver-dev` §3.2c), scoped to the capability under test, with a mutant killed to prove the FR constrains something |
| Crosses several features, runnable today | the (sub)story's path inventory | one inventory row yields one cross-feature FR, numbered `<ID> FR-N` on the contract so `check_fr_coverage.py` reads it unchanged |
| Touches an interface not yet defined | a deferred inventory row | names its blocking capability; gate 2 below fails that capability's delivery while the row is unwritten |

A single-feature path is **never** restated on the contract — that is `ADR-003`'s Type A, and
restating it is what made `INT-US-28` credit 41 unit tests to a seam with six claims.

### 2. The `-MIG` identifier

`INT-US-NN-MIG` (and `INT-US-NN-SFxx-MIG`) is a **new, additive** entry per (sub)story in scope: a
closable migration task. The `INT-US-NN` entry keeps its name and becomes the durable contract.

Additive rather than a rename because the two have different lifecycles — the migration finishes, the
contract keeps accruing deferred rows as capabilities are built — and one checkbox cannot mean both.
A `-MIG` line closes when the inventory exists, every runnable test is placed and green, and every
non-runnable path is recorded with its blocker. It does **not** wait for the story's unbuilt
capabilities, or US-6's could never close.

The grammar is hardcoded in five sites. **Probed rather than reasoned about, which changed the
answer from four to two:**

| Site | Behaviour on `INT-US-06-MIG` | Action |
|---|---|---|
| `scripts/tests.py:107` `INT_ID` | **no match** — anchored, two-digit, no `-MIG` and no `-SUB` | widened |
| `check_retirement_targets.py:57` `_RETIRED_ID` | matches but **TRUNCATES** to `INT-US-06` | widened |
| `check_retirement_targets.py:107` `_ENTRY_BULLET` | prefix match, and it is a boolean test | unchanged |
| `check_proof_tier.py:84` `_ENTRY` | `INT-US-[\w\-]+` captures it whole | unchanged |
| `check_comment_provenance.py:57` `_REGISTRY_ID` | truncates, but only presence matters | unchanged |

The truncation is the finding worth having. `_RETIRED_ID` fails **silently**: it captures a valid but
WRONG id, attributing a `-MIG` line's note to the base contract — the same mislabel its own docstring
already records for two live notes credited to their base contracts instead of the add-ons retired.
Reasoning about the pattern would have missed it, because it does match.

### 3. Two gates

**Gate 1 — no green without integration.** Extends `check_delivered_claims.py`, which already owns
"a `✅` nothing can verify" and already parses both the 4-space MVS plane and the 8-space add-on
plane. A fourth finding kind: a green unit holding closed features with **no integration contract at
all**.

**Absence is the whole rule.** `group_flag_findings` and `story_flag_findings` compare a flag with
the children that are present, so an *unchecked* contract already forces `🟡` and needs no new rule.
Neither can see a child nobody wrote.

**Zero-tolerance, not ratcheted — the design was wrong about this.** It assumed the rule would fire
on all 27 on day one. Measured once FR-2/FR-3 registered them: it fires on **none**, because those
units are `🟡` or their contracts are `[ ]`. There is nothing to carry forward.

A `-MIG` entry does not satisfy it. The migration entry is the task of building the inventory, not
the proof it produces.

**Gate 2 — a stale strict-xfail.** New `scripts/check_xfail_blockers.py`: any
`pytest.mark.xfail(strict=True)` whose named blocking capability is now `✅` in the capability matrix
is a finding. Zero-tolerance — there is no legacy set, because clause 4's markers do not exist yet.
Requires the marker's reason to name its blocker, which is therefore part of the contract rather
than a convention.

Both run at the `doc` gate: each is a question about registry state, not about a diff.

### 4. The registry

One dedicated roadmap section listing all 27 `-MIG` entries, added once and deleted once when
discharged. **Not** a line inside each of the 21 stories: that is 27 placement edits in and 27 out,
and misfiled registry insertions are what wrecked three commits on 2026-08-16.

The three `✅` entries citing no test file flip to `[ ]`. That is a reversal of three delivery
claims, and it is the honest reading of `check_proof_tier.py`'s own findings, which have been
recording them as debt rather than as done. **Consequence to handle in the same commit:** US-5's two
add-on groups are `🟢` because those children are `✅`, so `group_flag_findings` fires the moment
they flip; both groups become `🟡`.

## Non-Goals

- **Writing the 27 inventories.** Each is its own `-MIG` work item, ordered by capability cluster so
  a shared seam is decided once with every claimant visible — `B-SENS-02` alone is the only closed
  capability in six base contracts.
- **The 17 already-proven contracts.** They have tests and lack an inventory. A named follow-on
  ticket, not this one and not silence.
- **Rewriting the 13 delivered contracts' FR tables.** `finished-stories-immutable`; `ADR-004`
  governs what is written next.
- **Re-pointing the live `Proves:` citations.** All 20 belong to the proven 17; not one of the 26
  carries a `Proves:` tag. The re-pointing problem is entirely in the follow-on.
- **`check_retirement_targets.py`'s second question.** It asks whether a retirement's *destination*
  is unbuilt and should also ask whether the *sub-story* already ships something. Correct, and it
  reads group membership from `master_story_roadmap.md` rather than topic-doc prose — a prose-parsing
  attempt turned 3 findings into 8 by counting prerequisites as held features. Deferred, because
  `ADR-004` removes the retirements it would judge.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `-MIG` grammar | four gate scripts | Accept `INT-US-NN[-SFxx]-MIG` wherever an `INT-US` identifier is parsed | A `-MIG` entry is a first-class registry id; no gate reports it as malformed or invisible |
| FR-2 | Migration registry | `master_story_roadmap.md` | One dedicated section listing the 27 `-MIG` entries, each naming its (sub)story and its closed capabilities; the 5 missing contract ids minted alongside (`INT-US-10-SF01`, `-11-SF01`, `-15-SF01`, `-19-SF01`, and `-25-SF01` restored) | The batch is trackable in one place and removable in one edit |
| FR-3 | Honest delivery marks | roadmap | `INT-US-05-SF03`, `-05-SF04`, `-21-SUB` flip `✅` → `[ ]`; US-5's two affected groups flip `🟢` → `🟡` | No `✅` survives that cites no test file; `check_delivered_claims` and `check_proof_tier` agree with the registry |
| FR-4 | No green without integration | `check_delivered_claims.py` | Report a (sub)story marked green whose closed features have no integration/e2e evidence, ratcheted | `ADR-004` clause 5 is enforced rather than written down |
| FR-5 | Stale strict-xfail | `check_xfail_blockers.py` | Fail any `xfail(strict=True)` whose named blocking capability is `✅` in the matrix; require the reason to name a blocker | Clause 4's markers cannot decay into permanent exemptions |
| FR-6 | The method is written down | `specweaver-feature`, `-design`, `-implementation-plan`, `-dev` | The contract's lifecycle, the trigger, the inventory-to-task reading and the marker discipline, one per skill | A future (sub)story gets its contract without this ticket being re-read |
| FR-7 | Verifiable proof | test suite | Each gate is driven against a synthetic registry built to violate it and one built to satisfy it, and probed with a planted violation | Neither gate can ship inert, which `R-OWNER` and the morning mutation gate both did |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No behaviour change | Registry, skills and gate scripts only. Nothing under `src/` is touched |
| NFR-2 | Both gates are zero-tolerance | Measured, not assumed: gate 1 fires on nothing once FR-2/FR-3 land, so the ratchet the design planned would freeze zero and mean nothing. Gate 2 has no legacy set either |
| NFR-3 | Existing gates stay green | `doc` 11/11 and `cb` throughout; the `-MIG` widening must not change how any existing identifier resolves |
| NFR-4 | Probed, not asserted | Every gate is verified by planting a violation and watching it fail, then removing it — a passing gate and an inert gate look identical |

## Execution Order

1. FR-1 grammar widening — nothing else parses without it
2. FR-2 + FR-3 registry, one commit, since FR-3's group-flag consequence is immediate
3. FR-4 gate 1, ratcheted against the state FR-2/FR-3 create
4. FR-5 gate 2
5. FR-6 skills

## Delivery

| FR | State | Where |
|---|---|---|
| FR-1 `-MIG` grammar | ✅ | `tests.py` `INT_ID`, `check_retirement_targets.py` `_RETIRED_ID`, `check_roadmap_placement.py` `STORY_ID` — three sites, two found only by probing |
| FR-2 migration registry | ✅ | `## 🚚 Integration Migration (-MIG)`, 27 rows by capability cluster; 5 contract ids minted |
| FR-3 honest delivery marks | ✅ | 3 claims flipped, 4 group flags followed |
| FR-4 no green without integration | ✅ | `check_delivered_claims.unproven_green_findings`, zero-tolerance |
| FR-5 stale strict-xfail | ✅ | `scripts/check_xfail_blockers.py`, `doc` gate, zero-tolerance |
| FR-6 the method in the skills | ✅ | `specweaver-feature` Phase 0b owns the contract; `-design` hard-stops without one; `-implementation-plan` schedules from the inventory; `-dev` enforces the named blocker |
| FR-7 verifiable proof | ✅ | below |

## Verifiable Proof

`tests/unit/scripts/test_check_xfail_blockers.py`, additions to
`tests/unit/scripts/test_check_delivered_claims.py`, and the identifier-grammar cases in
`tests/unit/scripts/test_quality_runner.py` / `test_check_retirement_targets.py`. Each gate red
before its implementation, and each probed with a planted violation on the live tree.
