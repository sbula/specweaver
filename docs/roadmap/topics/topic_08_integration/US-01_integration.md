# US-01 Integration - Integration Contracts

## Base Story Contract (`INT-US-01`)
* **Status:** ✅ Complete
* **Integration Description:** The CLI (`E-UI-01`) must parse the file using Loom (`E-SENS-01`) and pass it to the Validation Engine (`E-VAL-01`), ensuring no unvalidated LLM generation occurs.
* **Verifiable Proof:** `tests/e2e/capabilities/assurance/test_standards_e2e.py`

## Sub-Story Add-Ons

*(Mirrored from the master roadmap 2026-07-24 — every add-on group carries its own integration story.)*

* **`INT-US-01-SF01` — Security Defenses:** *Pending Design.* Integrates `E-VAL-03` (AST Prompt Injection Sanitization, unbuilt).

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `E-VAL-03`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

* **`INT-US-01-SF02` — Enforce Internal Architecture:** *Pending Design.* Integrates `C-EXEC-01` ✅ + `C-EXEC-03` ✅ + `E-UI-04` (unbuilt).

  > **UN-RETIRED.** Ships `C-EXEC-01` ✅ and `C-EXEC-03` ✅; this story owns their integration and
  > e2e proof. `E-UI-04` is unbuilt and owns its own.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | The six macro-domains hold the packages they took in, and none of the pre-restructure top-level packages exists | single feature | `C-EXEC-03` | yes — **done** | — |
  | P-2 | Every import in `src/` and `tests/` resolves inside the new domains | single feature | `C-EXEC-03` | yes — **done** | — |
  | P-3 | Seam: `tach.toml` declares those same domains, and every path it names resolves | cross-module | `C-EXEC-03` + `C-EXEC-01` | yes — **done** | — |
  | P-4 | Seam: a forbidden upstream import fails the suite — at zero, not a baseline | cross-module | `C-EXEC-01` | yes — **done** | — |
  | P-5 | Seam: a soft-deprecated surface cannot be re-exposed through `interfaces:` | cross-module | `C-EXEC-01` | yes — **done** | — |
  | P-6 | Journey: a boundary violation in an *analysed* project becomes an ERROR finding in its review | cross-feature | `C-EXEC-01` | yes — **done** | — |
  | P-7 | Journey: that project's `context.yaml` boundaries are emitted as its own `tach.toml` and then enforced against it in one run | cross-feature | this contract, deferred | no | none — needs an e2e over the whole chain |
  | P-8 | The test tiers mirror `src/` 1:1, and `tests/e2e/` is organised only by capability | cross-feature | this contract, deferred | no | scope decision — see below |
  | P-9 | The architecture surfaces in the UI | cross-feature | `E-UI-04` (unbuilt) | no | `E-UI-04` owns this as its own FR |

  **Seventeen FRs across two capabilities, all cited, all behind killed mutants** —
  `check_fr_coverage.py` exits 0 for both. Three findings came out of it, and they are the same finding
  three times: **a guard that had stopped guarding, and nothing said so.**

  **1. `tach check` ran against a baseline of 95 violations.** Set 2026-05-25 (`07ce7544`) when the debt
  was real; `tach check` now reports zero. The slack outlived the debt by nearly three months and was not
  inert — importing `interfaces.cli` into `graph.lineage.scanner`, whose `depends_on` is empty, passed
  the entire suite, as would the next ninety-four. `CLAUDE.md` lists "no cross-layer imports" as a
  critical rule. Nothing checked it. Now zero.

  **2. `test_tach_keeps_runner_soft_deprecated` had never executed its assertion.** It searched the
  `interfaces` blocks for `from = "src.specweaver.assurance.validation"`; `tach.toml` sets
  `source_roots = ["src"]`, so its paths begin at `specweaver.`. The string never matched, the loop body
  never ran, and the test passed unconditionally — re-adding `runner` to the expose list passed the whole
  suite. Fixed, and it now asserts the block was *found*, so the same drift cannot return it to silence.

  **3. `C-EXEC-01` declared its requirements where no gate could read them.** FR1–FR4 were prose bullets
  (`**FR1:**`), and both requirement gates match `| FR-N |` table rows — so a capability with four
  declared FRs and eight committed sub-features counted as declaring nothing. Same class as
  `C-SENS-02`'s `_impl_plan.md` filenames: written down, invisible. Converted, wording preserved, and
  FR-5 added for SF-08, which shipped undescribed.

  **The common shape is worth stating once.** None of these three was a missing test. Each was a test,
  or a declaration, that *looked* like enforcement while enforcing nothing — a stale threshold, a
  never-matching string, a format the reader can parse and the gate cannot. They do not fail; they go
  quiet. Every one was found the same way: a mutant that should have died and did not. That is the whole
  argument for `ADR-004`'s citation requirement, and this pair of capabilities is where it paid.

  **P-8 is `C-EXEC-03`'s unfinished half, held open deliberately.** FR-7 claims 1:1 test parity — four
  test directories have no `src/` counterpart. FR-8 claims `tests/e2e/` moved from a flat tree into
  capability folders — `capabilities/` holds seven, and the flat tree it was to replace still sits beside
  it: four loose files and five layer-shaped directories. The guards use **named** exceptions rather than
  counts, so neither gap can grow by one, but neither is closed. Deciding which capability folder each of
  the nine remaining locations belongs to is a scope call, and nine mechanical moves inside a migration
  commit is how a restructure acquires a second unfinished half.

  One leftover was deleted rather than excepted: `tests/unit/graph_store/`, an empty `__init__.py`
  stranded when `graph/core/store` moved.

  **`INT-US-01-SF02-MIG` is discharged (2026-08-17); the contract stays open** on P-7, P-8 and P-9.

* **`INT-US-01-SF03` — Configurable Multi-Stage Reviews:** *Pending Design.* Integrates `E-VAL-02` ✅ + `E-VAL-04` (unbuilt, rubric-first on `C-VAL-05`) + `B-VAL-02` ✅.

  > **UN-RETIRED.** Ships `E-VAL-02` ✅ and `B-VAL-02` ✅; this story owns their integration and
  > e2e proof. `E-VAL-04` is unbuilt and owns its own.

* **`INT-US-01-SF04` — Mathematical Speed & Security (Rust):** *Pending Design.* Blocked on `A-VAL-04` (unbuilt).

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `A-VAL-04`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

* **`INT-US-01-SF05` — Rubrics-as-Content:** *Pending Design (minted 2026-07-24 audit).* Integrates
  `C-VAL-05` (unbuilt — middle-way first bite): wires the DAL-gated rubric files into the live
  battery/review surfaces once the capability lands.

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `C-VAL-05`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

