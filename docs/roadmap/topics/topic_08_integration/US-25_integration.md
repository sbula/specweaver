# US-25: Compliance & Constitution Governance - Integration Contracts

## Base Story Contract (`INT-US-25`)
* **Status:** ✅ Complete (2026-08-13) — contract written against already-delivered capabilities, not
  alongside new ones. `C-VAL-01`, `C-VAL-02`, `C-VAL-03`, `D-VAL-02` and `D-VAL-04` had all shipped
  ✅ and the epic was marked 🟢, while this document had never been written past
  `[Pending definition...]` and the roadmap marked the contract `✅` anyway — a
  **built-but-not-integrated** entry of exactly the shape `INT-US-21` exposed and closed. Found by
  `TECH-017`'s re-measurement (2026-08-13); the roadmap marker was corrected to `[ ]` the same day,
  then the seam was proven and it is now genuinely closed. Closing this contract closes the **US-25
  epic**.
* **Integration Description:** Two independent governance surfaces reach the agent, and both are
  proven to change its behaviour rather than merely to be storable. **(1) Constitution** —
  `sw constitution init/show/check` manages a project-wide `CONSTITUTION.md` (`C-VAL-01`) which is
  resolved by walk-up, size-capped via `sw config set-constitution-max-size`, and **injected into
  the prompt of every LLM-consuming command**: `review spec`, `review code` and `implement`. Absence
  of the file means no injection rather than a broken prompt, and a project-local file overrides the
  default. **(2) Domain profile** — `sw config set-profile <name>` (`C-VAL-02`) selects one of five
  preset bundles, and `sw check --level component` then loads **that profile's validation pipeline
  YAML** (`validation_spec_web_app`, `_library`, …) instead of `validation_spec_default`, with
  `--pipeline` and `--level feature` both overriding it. Each profile pipeline carries
  `extends: validation_spec_default`, so `D-VAL-02`'s YAML inheritance resolves as part of the same
  round trip. Layered on top, a nested `context.yaml` declaring `operational.dal_level` (`C-VAL-03`)
  makes the same spec that PASSES WITH WARNINGS under no boundary FAIL under `DAL_A`, while `DAL_E`
  leaves it passing — so the override is *strictness*, not merely *boundedness*. `D-VAL-04`'s
  standards scan upserts rather than duplicates across re-scans and honours `.specweaverignore`.
  **Deliberately delegated:** the code-level half of `C-VAL-03` — that a strict DAL changes the
  verdict on LLM-*generated* code — is `TECH-041`; it needs a scripted adapter because
  `sw implement` reaches the provider before any code-level enforcement runs, and it is named here
  rather than implied covered.
* **Verifiable Proof:** 75 tests across 9 integration/e2e files, all on the real CLI, all green.
  Written one file per line: the gates read this field to its end, and a proof declared as a single
  prose line was verified 3 files of 9 before `TECH-017` fixed the parser on 2026-08-13.
  * `tests/e2e/capabilities/workspace/test_constitution_e2e.py` (16) — injection asserted
    separately into the `review spec`, `review code` and `implement` prompts; a custom file
    overriding the default; **no file → no injection**; and the full `init` / `show` / `check`
    surface including oversize rejection and refuse-to-overwrite.
  * `tests/integration/interfaces/cli/test_cli_constitution.py` (8) — the CLI seam beneath it.
  * `tests/integration/interfaces/cli/test_profile_check_seam.py` (6) — asserts **which pipeline
    YAML was loaded**, via a spy wrapping the real loader so the round trip stays real. The
    `--pipeline` and `--level feature` cases name a profile whose YAML *differs* from the expected
    winner, so ignoring the override fails on the loaded name rather than passing on a shared exit
    code. Rewritten 2026-08-13: all six previously asserted `exit_code in (0, 1)`.
  * `tests/e2e/capabilities/workspace/test_domain_profile_e2e.py` (10) — the same seam through the
    full `sw config set-profile` → `sw check` journey, plus the profile CLI surface.
  * `tests/e2e/capabilities/workflows/test_dal_e2e_pipeline.py` (5) — unbound exits 0, the
    identical spec under `DAL_A` exits 1, under `DAL_E` exits 0 again, and the declaration is
    inherited by nested paths. The `DAL_E` case is the control that makes this mean *strictness*
    rather than *boundedness*.
  * `tests/e2e/capabilities/assurance/test_validation_dal_enforcement.py` (2) — strict-fails and
    lenient-passes at spec level.
  * `tests/e2e/capabilities/assurance/test_validation_pipeline_e2e.py` (13) — which rule IDs fire
    under a profile override and under a disable override (`D-VAL-02` inheritance).
  * `tests/e2e/capabilities/assurance/test_standards_e2e.py` (6) — re-scan changes the stored
    dominant pattern and leaves exactly one row per category (upsert, not insert).
  * `tests/integration/interfaces/cli/test_cli_standards_integration.py` (13) — the same, plus an
    ignored directory not shifting the dominant naming style (`.specweaverignore`).


## Sub-Story Add-Ons

* **Dynamic Risk Controls (`INT-US-25-SF01`)**
  * **Status:** ⬜ Pending Design
  * **Integration Description:** [Pending definition — the capabilities it would integrate
    (`D-VAL-02` Custom Rule Paths, `D-VAL-04` Adaptive Assurance Standards, `C-VAL-03` Dynamic Risk
    Rulesets) are all delivered ✅ and are exercised by the base contract above; what remains for
    this add-on is the scope decision, not the build.]
  * **Verifiable Proof:** [Pending]

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | A project defines its own validation pipeline by difference — `extends` with `override` / `remove` / `add` — and a cyclic chain is refused by name | single feature | `D-VAL-02` | yes — **done** | — |
  | P-2 | Seam: the project's own `D`-prefixed rule classes and its `.specweaver/pipelines/*.yaml` take precedence over the packaged ones, and stored settings are applied on top | cross-module | `D-VAL-02` | yes — **done** | — |
  | P-3 | A module declares its risk tier once, and everything beneath that boundary inherits it | single feature | `C-VAL-03` | yes — **done** | — |
  | P-4 | Seam: the project's `dal_definitions.yaml` is deep-merged over the packaged matrix, so a rule can be augmented or disabled per tier | cross-module | `C-VAL-03` | yes — **done** | — |
  | P-5 | Seam: freedom-from-interference is outsourced to the native boundary linter through the QA runner, merged with per-file `forbids` | cross-module | `C-VAL-03` | yes — **done** | — |
  | P-6 | An agent must propose a criticality per component; one is never arrived at by omission | cross-module | `C-VAL-03` | yes — **done** | — |
  | P-7 | Seam: the configured standards mode decides what the agent is told, and a project with nothing to learn from still gets defaults | cross-module | `D-VAL-04` | yes — **done** | — |
  | P-8 | Seam: prompt context is condensed to AST skeletons, and dependency neighbourhoods are answered from the in-memory graph | cross-module | `D-VAL-04` | yes — **done** | — |
  | P-9 | Journey: a DAL declared in `context.yaml` changes which rules run against a specific file, end to end | cross-feature | `TECH-041` | no | `TECH-041` — proven link by link, never as a chain |

  **Fourteen FRs across three capabilities, all cited, all behind killed mutants.** Two of the three
  had **no design document at all** or **no readable requirements**:

  - **`D-VAL-02`** shipped with an implementation plan and no design. Five FRs written from why it
    exists — a project's assurance rules are the project's business.
  - **`C-VAL-03`** declared five FRs as prose bullets (`**FR1 …**`), which both requirement gates read
    as none, since both match `| FR-N |` table rows. Second instance in this migration after
    `C-EXEC-01`. Converted, wording preserved.
  - **`D-VAL-04`** had a proper table and four uncited FRs.

  ### The finding that matters, and it is a safety one

  **`C-VAL-03` FR-2 had no test, and the mutant that exposed it was `default=DALLevel.DAL_E`.**

  FR-2 is the governance requirement: an agent proposes a DAL per component and an architect approves
  it. Its teeth are the *required* `proposed_dal` field on `ComponentChange` — that is what forces a
  proposal to exist at all. Giving the field a default passed the **entire suite**.

  `DAL_E` is the lowest criticality. So an agent that simply omitted the field would have had every
  component rated least-critical, and nothing would have looked wrong: no error, no missing key in the
  output, no proposal for an architect to reject. **A safety downgrade arriving as an absence.** In a
  capability whose whole purpose is DO-178C-shaped risk tiering, that is the most consequential gap this
  migration turned up. `test_a_component_without_a_proposed_dal_is_rejected` closes it.

  A default is not a neutral act when the field it fills is a risk tier.

  ### Two things measured and recorded as thin

  **`C-VAL-03` FR-4 has one test.** It covers a requirement that lets a project *disable* rules
  (`Rule_X: null`) inside a safety-tier matrix. **`D-VAL-04` FR-1 and FR-2 have one apiece.** The counts
  are recorded rather than smoothed over — a cited FR is not the same as a well-covered one, and this
  contract is the place that difference should be visible.

  **`D-VAL-02` FR-1 fails 71 files**, the widest mutant measured anywhere in this migration: the packaged
  pipelines use inheritance to build themselves, so disabling one directive breaks nearly every
  validation path. Against `C-VAL-03` FR-4's one, that spread is the real shape of these three
  capabilities — which the topic entries, listing components as equals, do not show.

  ### On this add-on's status

  The 2026-08-16 note above is still right that **no seam is waiting on anyone**: all three capabilities
  are delivered and now proven per-FR. What it could not know is P-9. `TECH-041` holds the one genuine
  end-to-end gap — the code-level DAL override is proven link by link and never as a chain — so the
  add-on is not merely "closed for want of scope"; it has exactly one open journey, and it is already
  ticketed.

  **`INT-US-25-SF01-MIG` is discharged (2026-08-17); the contract stays open** on P-9, which is
  `TECH-041`'s to close.

---

> **Why this contract was written after its capabilities shipped.** Recorded so the sequence is not
> read as the normal one. Every `C-VAL`/`D-VAL` capability under US-25 was delivered and marked ✅,
> and `master_story_roadmap.md` marked `INT-US-25` ✅ too — while this file said `⬜ Pending` with
> `[Pending definition...]` and `[Pending]` proof. The two documents contradicted each other for
> months. `check_story_preconditions.py` has contained a check that fails exactly this shape since
> it was written, and never fired, because it only runs when a human passes that story ID and
> nobody ever passed `INT-US-25` — which is why `scripts/check_proof_tier.py` (`TECH-017`,
> 2026-08-13) sweeps every contract instead of taking a story argument.
>
> The lesson is not "write the contract earlier" but **a delivered capability is not an integrated
> one**, and only a contract journey tells them apart. Six tests spanned this seam and all six
> asserted `exit_code in (0, 1)`; with the domain-profile lookup disabled the whole capability was
> dead and the suite reported 10 passed.

  > **CLOSED EMPTY 2026-08-16 — nothing moved, because nothing was left.** `ADR-003` dropped
  > `INT-US-25-SF01`'s roadmap placeholder on 2026-08-13 with the note *"it moves to the capability
  > that builds it"* — naming nobody. That is the unfalsifiable prose the ADR set out to delete,
  > wearing the ADR's own name, and `scripts/check_retirement_targets.py` now rejects the shape.
  >
  > Re-checked 2026-08-16: `D-VAL-02`, `D-VAL-04` and `C-VAL-03` are all delivered **and** exercised
  > by the base contract above, so no seam is waiting on anyone. What the entry describes as
  > remaining is a **scope decision**, not a build — this add-on is closed for want of scope, and
  > re-opening it means deciding what it should do, not integrating what already works.

