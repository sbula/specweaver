# Design: Delivered Add-On Re-Validation Against an Integrated Base (INT-US-21-SUB / C-INTL-01)

- **Feature ID**: TECH-018
- **Epic**: Topic 07 (Technical Debt)
- **Status**: 🟢 **AUDIT DELIVERED 2026-08-13** — audit-only ticket, discharged by the audit below.
  No remediation was in scope and none was performed. Findings are listed in §Findings and become
  new tickets.
- **Origin**: INT-US-21 design `AD-9` (user mandate, 2026-07-25), relocated out of the feature on
  2026-07-26 during the INT-US-21 scope re-cut

## Problem Statement

`C-INTL-01` / `INT-US-21-SUB` (Recursive Planning / Iterative Decomposition) was delivered and
marked ✅, and its integration claim reads *"covered by `pytest -m integration` and the
`FeatureDecomposer` suite"*. That claim was never exercised through a real
`sw run feature_decomposition` journey, because **no such journey could run at the time**:
`draft+feature` and `validate+feature` were never registered, so the shipped pipeline died at
step 1. The add-on was therefore proven against a path that did not execute end-to-end.

INT-US-21 then changed the ground underneath it, introducing seams the add-on never saw:
`RunContext.decomposition` (`context.plan` no longer carries the plan), the persisted
`<stem>_decomposition.yaml` schema, approve-on-resume gate semantics, stub component spec paths,
and the CLI journey itself.

Three questions needed answering **with evidence, not inspection**: is the add-on's claimed scope
still valid; does it still cover what US-21 needs; does it cooperate with the base's new seams.

## Audit Result — measured 2026-08-13

### Q1. Is the claimed scope still valid? **No — and it never was.**

The add-on is registered as **"Recursive Planning"**, and its integration description states that
`C-INTL-01` *"implements iterative decomposition, generating a structured DecompositionPlan by
resolving the AST graph into sub-tasks."* Measured against `src/`, the shipped capability does
none of those three things.

| Claim | What the code does |
|---|---|
| **Recursive** | `FeatureDecomposer.decompose` (`workflows/planning/decomposer.py:65`) builds one prompt, makes **one** `llm.generate` call, parses one plan, returns. No self-invocation, no depth parameter, no re-entry. |
| **Iterative** | No loop of any kind, in the decomposer or its caller. **One call site in all of `src/`** — `core/flow/handlers/decompose.py:66` — invoked once per run. |
| **Resolving the AST graph into sub-tasks** | The graph is **prompt context, not a source of sub-tasks**: the call site passes `topology_contexts=[context.graph.topology] if context.graph.topology else None`, which `PromptBuilder.add_topology` appends to the prompt. The components come from the LLM reading the feature spec's markdown. |

The data model closes it: `DecompositionPlan` is **flat** — `components: list[ComponentChange]`,
each with `dependencies: list[str]`. That is a one-level DAG of names. **There is no nesting to
recurse into**, so recursion is not merely absent from the implementation, it is unrepresentable
in the type the capability returns.

The base contract corroborates independently, from the opposite direction: its delivered journey
is specified and proven to cost **"exactly one LLM call."** A recursive decomposition cannot cost
one call.

This is a **description defect, not a functional one.** The single-pass decomposer works, and is
what every consumer actually depends on.

### Q2. Does it still cover what US-21 needs? **Yes — incidentally.**

The base contract needs exactly one flat plan produced by one LLM call, which is what the
capability provides. Nothing in the integrated base asks for recursion, and `C-FLOW-12` /
`INT-US-21-SF02` (autonomous DAG *execution*) consumes the flat component list as-is. So the
mismatch in Q1 has no consumer today — which is precisely why it survived.

### Q3. Does it cooperate with the base's new seams? **Yes, and it is already proven.**

`tests/e2e/capabilities/workflows/test_feature_decomposition_e2e.py` — 801 lines, 24 tests —
drives the real CLI through the journey the add-on was never exercised on, covering every seam
this ticket listed: cross-session rehydration matched against the on-disk artifact (E5), the
persisted artifact and stub inventory (E1), stub no-overwrite (E7), approve-on-resume across three
sessions (E1), re-run reusing the artifact identity (E10), refusal to resume a finished run (E11),
and interrupt survival with handover saved and telemetry flushed (E12).

**That suite landed in `ccdda8f8` and `39aa3860` on 2026-07-28 — two days after this ticket was
filed on 2026-07-26.** It is, essentially verbatim, this ticket's second candidate approach
("drive the add-on's recursion through the real `sw run feature_decomposition` CLI journey, now
possible; it was not when the add-on shipped"), delivered by the base contract's own SF-03 without
either side noticing it discharged the audit's hardest question.

### Q4 (not asked, found while answering Q3). The proof claim is a tier mismatch.

The add-on's Verifiable Proof reads *"covered by integration testing under `pytest -m integration`
and the `FeatureDecomposer` suite."* Both halves fail on measurement:

- **The "`FeatureDecomposer` suite" is `tests/unit/workflows/planning/test_decomposer.py` — 4 unit
  tests**: returns a plan, LLM raises, Pydantic validation error, and one assertion on the
  instruction template's wording. There is no integration or e2e file dedicated to the add-on.
- **`pytest -m integration` covers it in name only.** Exactly two integration files mention
  `FeatureDecomposer`, and **both patch it out** —
  `tests/integration/engine/test_caller_migration_integration.py:76` and
  `tests/integration/core/flow/handlers/test_decomposition_artifacts_integration.py:151` each
  `patch("...handlers.decompose.FeatureDecomposer")`. It is the **doubled edge** in those tests,
  not the subject. Zero integration tests execute `FeatureDecomposer.decompose`.

This is the exact defect class `TECH-017` exists to name — a contract claiming integration proof
while pointing at unit tests — so it is reported here and handed to that ticket rather than
double-covered.

## Findings

Audit-only: each becomes a NEW ticket, never an edit to `INT-US-21-SUB`'s entry
(finished-stories-immutable). None is a live defect; both are registry-accuracy defects.

1. **`INT-US-21-SUB` / `C-INTL-01` claims recursion the code does not implement.** → filed as
   **[`TECH-038`](../TECH-038/TECH-038_design.md)** (2026-08-13). The registry
   describes a recursive/iterative decomposer resolving the AST graph into sub-tasks; the shipped
   capability is a single flat LLM call returning a non-nestable plan. Decide which is wrong — the
   description or the scope — and correct the one that is. Note the naming divergence already
   recorded as OQ-1 (`INT-US-21-SUB` here vs `INT-US-21-SF01` in the master roadmap) sits on the
   same entry and should be considered together.
2. **The add-on's Verifiable Proof cites tests that do not prove it** (Q4). Both cited sources are
   either unit-tier or mock the subject away.

## Non-Goals — held

- **No remediation.** Audit and report only. ✅ Held — no `src/` change was made by this ticket.
- **No edits to `INT-US-21-SUB`'s entry or its docs, not even notes.** ✅ Held —
  `US-21_integration.md` was not modified; the result lives here and in `topic_07`.
- Not a re-audit of the whole topic_08 contract set — that is `TECH-017`. ✅ Held.
- Not blocking INT-US-21 closure. ✅ Moot — the epic closed 2026-07-28.

## Coordination with `TECH-017`

The ticket required that the two not double-cover `INT-US-21-SUB`. Discharged: `TECH-017`'s
per-story matrix should **exclude** `INT-US-21-SUB` and take finding 2 above as its result for
that add-on.

## What made this cheap

The audit cost one session rather than the "unknown size" the ticket feared, for one reason worth
recording: **the evidence it needed was built by someone else in the meantime.** Its second
candidate approach — drive the journey through the real CLI — was delivered by INT-US-21 SF-03 two
days after filing. An audit ticket whose precondition is "story X ships" should be re-measured
before it is planned, not planned from its filing-day evidence; the same re-measurement corrected
three of `TECH-017`'s findings on the same day.
