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

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `E-UI-04`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.
  >
  > **Corrected 2026-08-16.** This note originally also named `C-EXEC-01` and `C-EXEC-03`, both
  > delivered — and a delivered story cannot accept an FR. Neither needed to: layer enforcement is
  > already live in the gates, and the add-on is blocked solely on `E-UI-04`, which is unbuilt and
  > will therefore write the seam test before its code. See `ADR-003`'s 2026-08-16 addendum.

* **`INT-US-01-SF03` — Configurable Multi-Stage Reviews:** *Pending Design.* Integrates `E-VAL-02` ✅ + `E-VAL-04` (unbuilt, rubric-first on `C-VAL-05`) + `B-VAL-02` ✅.

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `E-VAL-04` (rubric-first on `C-VAL-05`), which
  > owns its own integration and e2e proof as FRs rather than a separate add-on restating them.
  >
  > **Corrected 2026-08-16.** This note originally also named `E-VAL-02`, which is delivered and
  > cannot accept an FR. It did not need to: standards auto-discovery is already wired into the
  > implement, review and flow CLIs, and the add-on is blocked solely on `E-VAL-04`, unbuilt.
  > See `ADR-003`'s 2026-08-16 addendum.

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

