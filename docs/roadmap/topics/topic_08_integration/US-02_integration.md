# US-02 Integration - Integration Contracts

## Base Story Contract (`INT-US-02`)
* **Status:** ✅ Complete (2026-07-23) — [design](../../features/topic_08_integration/INT-US-02/INT-US-02_design.md); SF-01 (feedback-aware draft→validate→review inline chain) + SF-02 (composition-root provider seam, TTY-gated / headless park exit 0) + SF-03 (verifiable proof) all committed. Closing this contract closes the **US-2 epic** (US-21 now integration-only).
* **Integration Description:** The interactive loop (`E-INTL-02`) must seamlessly hand off the generated context to the Review Engine, ensuring no manual copy-pasting is required.
* **Verifiable Proof:** `tests/e2e/capabilities/workflows/test_int_us_02_drafter_e2e.py` — 7 scenarios on the REAL CLI surfaces (scripted provider via the SF-02 seam + scripted adapter; real Drafter, real battery via D-VAL-02 mechanical-only local preset, real reviewer + gate loop): accept · reject→re-draft→accept · headless park (exit 0) · retries exhausted · provider crash · park→manual-spec→resume · rejection-park→edit→resume.

## Sub-Story Add-Ons

* **`INT-US-02-SF01` — Surgical Spec Refactoring:** *Pending Design.* Depends on `D-SENS-05` (Markdown AST Mutators, unbuilt).
* **`INT-US-02-SF02` — Remote UI Integration:** *Pending Design.* Depends on `D-UI-04` (REST API Interactive Authoring, unbuilt).
* **`INT-US-02-SF03` — Grill-Style Agentic Drafting:** *Pending Design (minted 2026-07-22).* **Integrates the
  capability `D-INTL-07`** (Agentic Interview Drafting — adaptive grilling interview + `/to-spec`-style
  synthesis, rubric-content-driven) into the drafting flow via the `C-FLOW-11` draft-step dial. Like every
  add-on, the SF is **integration only** — the engine build lives in the capability. The base contract's
  gates (S-battery → semantic review → bounded loop, provider wiring, proof) are reused verbatim: they gate
  whatever engine produced the spec. Whether `D-INTL-07` **replaces** the `E-INTL-02` engine or leaves it as
  the oneshot/headless fallback mode is decided at `D-INTL-07`'s design intake. **If "replace": the
  decommission duties are part of this SF's definition of done** — delete the superseded `E-INTL-02` code
  AND remove its entries from the living registry (matrix/topic/roadmap), leaving only the unchanged spec
  file in git as the historical record (see `D-INTL-07` §Mandatory Decommission Duties). **Blocked on
  `C-FLOW-11`** (hard) + `C-VAL-05` (soft); deliberately sequenced AFTER the base contract closes US-2
  (timeline decision Option A, 2026-07-22).
