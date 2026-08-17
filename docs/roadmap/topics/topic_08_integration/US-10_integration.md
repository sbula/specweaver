# US-10: The Monolith Dependency Visualizer - Integration Contracts

## Base Story Contract (`INT-US-10`)
* **Status:** ⬜ Pending
* **Integration Description:** [Pending definition...]
* **Verifiable Proof:** [Pending]

## Sub-Story Add-Ons

* **`INT-US-10-SF01` — Code-to-Spec Drift Checking:** the add-on's contract under `ADR-004`.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | Pure-logic comparison of a file's signatures against its plan: parameters that moved, public methods the plan never authorised, planned methods absent | single feature | `B-VAL-01` | yes — **done** | — |
  | P-2 | Seam: the handler parses the target with tree-sitter, validates the plan YAML into a `PlanArtifact`, and hands both to a detector that touches neither disk nor DB | cross-module | `B-VAL-01` | yes — **done** | — |
  | P-3 | Seam: `sw drift check` builds a one-step `DETECT`/`DRIFT` pipeline and the runner dispatches it to the handler | cross-module | `B-VAL-01` | yes — **done** | — |
  | P-4 | Seam: `--analyze` reaches an LLM adapter through `RunContext.model.llm`, and **only** on the flag | cross-module | `B-VAL-01` | yes — **done** | — |
  | P-5 | Journey: a plan the planner actually generated carries `expected_signatures` the drift engine can compare against | cross-feature | this contract, deferred | no | none — needs a planner fixture, not a feature |
  | P-6 | A non-Python target is *distinguishable* from a clean one | cross-feature | this contract, deferred | no | needs a scope decision — see below |

  **`B-VAL-01`'s five surviving FRs are cited and each is behind a killed mutant** —
  `check_fr_coverage.py B-VAL-01` exits 0. Two findings came out of getting there.

  **FR-5's word "only" was the untested half.** The FR says root-cause analysis runs *only* when
  `--analyze` is passed. Deleting the guard entirely — so every drifted file silently bought an LLM
  call — passed the whole suite, because the single test with an LLM attached also passed the flag.
  A guard is proven by the path it *blocks*; that path had no test.
  `test_drift_handler_does_not_analyze_without_the_flag` counts calls on the adapter and closes it.

  This is the **third** instance of one shape in this migration: `E-UI-02` FR-1 (a page that always
  renders), `B-INTL-02` FR-3 (a call that always succeeds), and now a flag that was never withheld.
  Each asserted the outcome it wanted and never the alternative, so each admitted a mutant that did
  strictly less work. Worth stating plainly because it is not a coincidence of three authors: it is
  what happens when a test is written from the feature's happy path rather than from its contract.

  **FR-2 is deleted from the design, and the descope was already on record.** It claimed the plan
  would be fetched "via the file's lineage UUID"; `--plan` is a required option and nothing in the
  path touches lineage. `B-VAL-01_sf02_implementation_plan.md` §Open Questions had weighed exactly
  that mechanism and recommended the flag instead — *"keeps it 100% fast, avoids globbing, and is
  explicit"* — which is what shipped. **The decision never travelled from the plan back to the design**,
  so the design kept advertising a resolution path the CLI cannot take. No gate compares an FR against
  a plan's own open questions.

  P-5 waits on a fixture, not a feature: `expected_signatures` is populated by the planner's prompt,
  and no test carries a real planner output into the drift engine, so the two halves of the contract
  are only ever exercised against hand-written plans.

  P-6 is a **limitation, not a contradicted FR** — FR-1 makes no language claim. The handler returns
  `PASSED` with `drift_count: 0` for any target whose suffix is not `.py`, so a polyglot repository's
  drift check reports clean rather than unchecked, and a caller cannot tell the two apart. The AST
  layer beneath it is polyglot (java, kotlin, rust, typescript parsers all ship). Same shape as
  `TECH-061` in the graph, different module. **Deliberately not ticketed yet**: changing a `PASSED`
  into anything else changes what a pipeline does, which is a scope decision, and filing a ticket is
  not the same as taking it.

  **`INT-US-10-SF01-MIG` is discharged (2026-08-17); the contract stays open** on P-5 and P-6.
