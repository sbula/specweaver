# Design: Delivered Add-On Re-Validation Against an Integrated Base (INT-US-21-SUB / C-INTL-01)

- **Feature ID**: TECH-018
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: INT-US-21 design `AD-9` (user mandate, 2026-07-25), relocated out of the feature on
  2026-07-26 during the INT-US-21 scope re-cut

## Problem Statement

`C-INTL-01` / `INT-US-21-SUB` (Iterative Decomposition) was delivered and marked ✅, and its
integration claim reads *"covered by `pytest -m integration` and the `FeatureDecomposer` suite"*.
That claim was never exercised through a real `sw run feature_decomposition` journey, because **no
such journey could run at the time**: `draft+feature` and `validate+feature` were never registered,
so the shipped pipeline died at step 1 (see INT-US-21 §Research Findings, gap 1). The add-on was
therefore proven against a path that did not execute end-to-end.

INT-US-21 changes the ground underneath it. The base contract introduces seams the add-on never saw:

- `RunContext.decomposition` (new field; `context.plan` no longer carries the decomposition plan)
- the persisted `<stem>_decomposition.yaml` schema, serialized `model_dump(mode="json")`
- approve-on-resume gate semantics (`resume` past a HITL gate now advances instead of re-parking)
- stub component spec paths
- the `feature_decomposition` CLI journey itself

Three questions need answering with evidence, not inspection: is the add-on's claimed scope still
valid; does it still cover what US-21 needs; and does it cooperate with the base's new seams?

**Why this is a ticket and not a clause in INT-US-21.** As `AD-9` it was a gate on the epic going
🟢 — an audit of a *different, delivered* story blocking closure of this one. The reasoning was
sound; the location was not. Auditing story A must not hold story B hostage, and an audit whose
size is unknown cannot sit on a critical path.

## Candidate Approaches (not yet designed)

- Re-run the add-on's existing integration suite against the integrated base and diff behaviour.
- Drive the add-on's recursion through the real `sw run feature_decomposition` CLI journey (now
  possible; it was not when the add-on shipped) and compare against its documented claims.
- Claim-by-claim matrix: each `INT-US-21-SUB` contract claim vs what a test actually proves —
  the same shape as `TECH-017`'s deliverable, scoped to one add-on.

## Non-Goals (proposed, pending design)

- **No remediation.** Audit and report only.
- **No edits to `INT-US-21-SUB`'s entry or its docs**, not even notes — finished stories are
  immutable. Every finding becomes a NEW story or its own `TECH-XXX` ticket.
- Not a re-audit of the whole topic_08 contract set — that is `TECH-017`.
- Not blocking INT-US-21 closure.

## Next Step

Run the `specweaver-design` skill. Sequence **after** INT-US-21 SF-03 is committed, since the
integrated base is the thing being audited against. Related: `TECH-017` (integration-contract proof
audit, same family — coordinate so the two do not double-cover `INT-US-21-SUB`), `TECH-014`
(fan-out `RunContext` isolation, which the add-on's recursion is exposed to).
