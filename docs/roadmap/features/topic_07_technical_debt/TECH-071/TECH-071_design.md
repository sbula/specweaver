# Design: Docs and Code Disagree in 60 Places

- **Feature ID**: TECH-071
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-09-25, the docs rewrite to the short format. Agents checked doc claims against
  `src/` while rewriting 395 docs and recorded every disagreement. The rewrite changed no code and no
  FR text. Census: [doc_code_discrepancies_2026-09-25.md](../../../../analysis/doc_code_discrepancies_2026-09-25.md).

## Problem Statement

About 60 places where a design, plan, guide or architecture doc says one thing and the code does
another. For each one, **which side is wrong is not yet known**. Six groups:

| Group | Count | What it means |
|---|---|---|
| A — built, never runs in production | 14 | A feature is marked delivered but its path is dead or missing (e.g. `GraphContext.stale_nodes` is never written, so the incremental test bypass never runs; C-FLOW-06 is ✅) |
| B — FR text vs code | 15 | The requirement says X, the code does Y (e.g. B-INTL-09 FR-8 `> 3` vs `>= 3`; B-VAL-02 exit `1` vs `42`) |
| C — proof missing | 5 | An FR or NFR with no test, or a planned test file that does not exist |
| D — status and tracker drift | 6 groups | ⬜ / DRAFT / "awaiting approval" for work on `main` |
| E — cells the rewrite changed | 2 | Two tracker cells flipped by an agent; need the owner's confirmation |
| F — registry and ownership | 16 | FR ownership conflicts, orphan bullets, dead names and paths |

Several group-A items are gaps in delivered work, so they are defects: `finished-stories-immutable`
bars editing the closed stories, which is why they sit here.

## Approach (proposed, pending design)

Per finding, in this order:

1. **Investigate.** Read the design's intent, the FR, the code and the tests. Establish what the
   system should do.
2. **Decide which side is wrong** — code, doc, or both. Where the answer changes what the product
   does (a descope, a behaviour change, a flag flip), it is the user's call (`T-DIVERGE`, `T-SCOPE`,
   `T-PROVEN`). Put it to the user; do not default it.
3. **Fix.** Code wrong → a failing test first, then the fix. Doc wrong → correct the doc, keeping
   the FR row start and table shape the gates parse. Descoped → delete the FR row so the descope is
   visible.
4. **Record** the decision beside the fact it governs, marked `[agreed <date>]`, and tick the row in
   the census.

Group A first: each item is a feature that looks delivered and is not. Group D is mechanical once
each tracker cell is checked against `git log`.

## Non-Goals (proposed, pending design)

- The TECH tickets in topic 07 were not part of the rewrite; their docs were not checked.
- No new features. A group-A item resolved as "build it" becomes its own ticket or capability.
- Line refs that have merely moved are not findings; the rewrite already marked them "Since moved".

## Guardrail to ship

A doc gate cannot tell whether prose matches code. What can be checked: every Progress Tracker cell
marked ⬜ whose sub-feature's plan says COMPLETED, and every plan `**Status**: DRAFT` whose tracker row
is all ✅ — the group-D pattern. Design decides whether that check is worth building.

## Next Step

Run `specweaver-design` on this ticket. Start with group A; put each code-or-doc decision to the user.
