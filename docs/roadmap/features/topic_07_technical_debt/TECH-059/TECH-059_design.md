# Design: Registry IDs and History in Production Comments

- **Feature ID**: TECH-059
- **Epic**: Topic 07 (Technical Debt)
- **Status**: APPROVED <!-- decisions settled by user interview 2026-08-17 (grill-me) -->
- **Origin**: raised by the user 2026-08-17 while agreeing `ADR-004` — *"code is a document of the
  present, no history"*

## Problem Statement

Production code carries **256 registry-ID references across ~130 files of `src/`**, plus about 41
comments whose content is itself retrospective. They are provenance: a note saying which ticket
caused a line to exist.

| Family | References | Files |
|---|---|---|
| `INT-US-NN` | 104 | 43 |
| `TECH-NNN` | 109 | 68 |
| Capability (`[A-E]-XXX-NN`) | 44 | 23 |

Two shapes occur. The overwhelming majority — roughly 215 — are an ID **prefixed onto a
present-tense statement**, where stripping the prefix leaves a working comment:

```python
# INT-US-24 FR-3: a scenario verification that executed zero tests proves nothing
# INT-US-09: rebind the execution root to the worktree source tree so untrusted-
```

The remainder are **wholly retrospective** and leave nothing when the ID goes:

```python
# Split out of ``handlers/decompose.py`` by INT-US-21 SF-02 CB-2, which took that file to 586 lines
```

**Why it is debt rather than taste.** A provenance prefix adds nothing at the point of reading: the
reader needs to know what the line does now, and git already holds who asked for it. Worse, the
reference rots independently of the code beside it — `ADR-004` has just moved the meaning of every
`INT-US` entry, so 104 of these references now name a ticket whose scope is not what the comment's
author meant. Nothing in the repo reads them, so nothing catches the drift.

## Decision

Strip the ID from a comment that carries a present-tense statement; delete the comment outright when
its content is history. Scope is **`src/` only**, all three ID families, in one mechanical sweep.

## Non-Goals

- **`scripts/` and `tests/`.** Deliberately out of scope for now. Their docstrings often record the
  measurement that justifies a rule, and that account is frequently the only thing stopping a future
  agent deleting the rule as pointless — `check_roadmap_placement.py` exists *because* its
  convention was once unwritten. Whether that is present-tense justification or history is a
  separate decision.
- **Comment density.** Deleting explanatory comments that happen to be long is a different and much
  larger judgment. Only the ID and the retrospection go.
- **`Proves:` citations.** In `tests/`, and machine-read by `check_fr_coverage.py` and
  `_citations.py`. They are a live contract, not provenance.
- **Behaviour.** Not one non-comment line changes.

## Approach

1. Enumerate every `src/` comment and docstring line matching the three ID families, plus the
   retrospection markers (`previously`, `supersede`, `no longer`, `formerly`, an ISO date).
2. Per site, classify: **strip** (a present-tense statement survives) or **delete** (nothing does).
3. Apply, one commit.
4. **Assert the diff touches comment lines only** — no change to any non-comment line — as an
   executable check rather than by eye. This is the guardrail that makes a ~130-file diff reviewable.
5. Full suite plus `quality.py cb`.

## Guardrail

The rule regrows without one, which is the failure mode of every discipline-only clause in this repo.
`scripts/check_comment_provenance.py` is zero-tolerance over `src/` and runs at `quick` (diff-scoped)
and `cb`/`sf`/`feature` (repo-wide).

**Not a rule inside `check_conventions.py`, as first planned.** That file sits at exactly 600 lines —
its RED ceiling — so a ninth rule cannot be added without shaving the prose that explains the other
eight, and `TECH-020` records buying headroom by condensing comments as the pattern to stop
repeating. R6, R7 and R8 were each moved to a sibling for the same reason; this rule gets its own
gate instead.

Zero-tolerance rather than ratcheted: the sweep reached zero, so there is no legacy set to carry, and
a ratchet at zero is a slower way of saying the same thing.

## Verifiable Proof

`tests/unit/scripts/test_check_comment_provenance.py` — 17 tests. Every ID family is caught in a
comment and in a docstring; an ID in a **string literal** is not, because that is behaviour;
validation rule IDs (`C09`, `S07`) are not, because they are domain vocabulary; an unparseable file
exits non-zero rather than passing silently; and the live `src/` tree scores zero.

Probed rather than assumed: a planted `# TECH-999` comment in `commons/timestamps.py` turns the `cb`
gate red, and removing it turns it green again.
