# US-22: Polyglot Contract Enforcement - Integration Contracts

## Base Story Contract (`INT-US-22`)
* **Status:** ⬜ Pending — migration `INT-US-22-MIG` discharged 2026-08-17; the contract stays open
* **Integration Description:** US-22 proves a Python microservice did not break a Rust worker's
  REST/gRPC contract. It holds **two** closed capabilities — `A-VAL-01` (Protocol/Schema Analyzers)
  and
  `C-VAL-04` (Traceability Matrix Check) — with `A-VAL-04` (Rust PyO3 validations) unbuilt.
* **Verifiable Proof:** P-1 and P-2 by `check_fr_coverage.py A-VAL-01` and `... C-VAL-04`, both exit
0.

### Path Inventory (`ADR-004`)

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | `.proto` / OpenAPI schemas parsed and analysed | single feature | `A-VAL-01` | yes — **already passed its ledger** | — |
| P-2 | Spec requirements enumerated, `@trace` tags parsed, compared, enforced | single feature | `C-VAL-04` | yes — **done** | — |
| P-3 | A schema change in one service surfaces as an untraced requirement in another | cross-feature | this contract, deferred | no | `A-VAL-04` |
| P-4 | Journey: prove a Python service did not break a Rust worker's contract | cross-feature | this contract, deferred | no | `A-VAL-04` |

**Two closed capabilities that do not meet yet.** `A-VAL-01` analyses protocol schemas; `C-VAL-04`
compares spec requirements against `@trace` tags in test code. Neither reads the other — the
cross-service comparison P-3 describes needs the deep contract checking `A-VAL-04` is for, and that
is
unbuilt. Third story in this migration where two closed features coexist without a runnable path
between them (`US-6`, `US-19`, and now `US-22`), which is worth noting as a pattern rather than an
accident: a story's capabilities are chosen for the journey, and the journey usually needs the piece
that is missing.

**`INT-US-22-MIG` is discharged; the contract stays open** until `A-VAL-04` lands.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
