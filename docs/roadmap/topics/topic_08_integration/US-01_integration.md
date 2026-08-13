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
  > The scope above is NOT descoped — it moves to `C-EXEC-01`, `C-EXEC-03` and `E-UI-04`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

* **`INT-US-01-SF03` — Configurable Multi-Stage Reviews:** *Pending Design.* Integrates `E-VAL-02` ✅ + `E-VAL-04` (unbuilt, rubric-first on `C-VAL-05`) + `B-VAL-02` ✅.

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `E-VAL-02`, `E-VAL-04` and `C-VAL-05`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

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

